"""The read-only MCP server: the only way the agent can look at the cluster.

Six tools, each with fixed, validated parameters and a timeout. None of them can change anything: there is
no shell, no kubectl, no write call, and the Kubernetes tools run as a ServiceAccount that may only
get/list/watch (and never read Secrets or exec into pods).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from ai_sre_agent.config import Settings

from . import gitops, observability
from .kube import Kind, Kube
from .limits import check_k8s_name, check_namespace, check_repo_path, clamp, parse_duration, with_timeout

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)
MAX_WINDOW = timedelta(hours=6)

INSTRUCTIONS = """\
Read-only tools for investigating incidents on the voting stand (Kubernetes, Kafka/Strimzi, PostgreSQL on
CloudNativePG, Redis, KEDA, deployed by Argo CD from the voting-gitops repository, branch lab).
Every answer is bounded: long results are truncated and say so. Nothing here can change the cluster."""


def build_server(settings: Settings) -> MCPServer:
    prometheus = observability.HttpApi(settings.prometheus_url, settings.http_host_header, settings.tool_timeout_s)
    loki = observability.HttpApi(settings.loki_url, settings.http_host_header, settings.tool_timeout_s)
    kube = Kube(settings.agent_kubeconfig)
    timeout = settings.tool_timeout_s

    @asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[None]:
        try:
            yield
        finally:  # the clients are recreated on first use if the server is entered again
            await prometheus.aclose()
            await loki.aclose()
            await kube.aclose()

    server = MCPServer("ai-sre-agent", instructions=INSTRUCTIONS, lifespan=lifespan)

    @server.tool(annotations=READ_ONLY)
    async def prometheus_query(
        query: Annotated[str, Field(description="PromQL expression", max_length=2000)],
        lookback: Annotated[
            str | None,
            Field(description="Look back this far as a range query (e.g. 30m, 2h; max 6h). Omit for an instant query."),
        ] = None,
        step: Annotated[str | None, Field(description="Range query resolution, e.g. 30s. Default: ~60 points.")] = None,
    ) -> dict[str, Any]:
        """Run a PromQL query against Prometheus: instant (current value) or over a time range.

        Useful metrics on this stand: kube_pod_container_status_* and kube_deployment_* (kube-state-metrics),
        container_memory_working_set_bytes, traefik_service_requests_total{exported_service=...},
        kafka_topic_partition_*, kafka_consumergroup_lag, cnpg_* (PostgreSQL), worker_votes_total, ALERTS.
        At most 30 series and 60 points per series are returned.
        """
        window = parse_duration(lookback, maximum=MAX_WINDOW, name="lookback") if lookback else None
        resolution = parse_duration(step, maximum=timedelta(hours=1), name="step") if step else None
        return await with_timeout(
            observability.prometheus_query(prometheus, query, window, resolution), timeout, "Prometheus"
        )

    @server.tool(annotations=READ_ONLY)
    async def loki_query(
        query: Annotated[
            str,
            Field(description='LogQL, e.g. {namespace="voting", app="worker"} |= "error"', max_length=2000),
        ],
        since: Annotated[str, Field(description="How far back, e.g. 15m, 1h (max 6h)")] = "15m",
        limit: Annotated[int, Field(description="Maximum log lines (1-300)")] = 100,
    ) -> dict[str, Any]:
        """Search container logs in Loki, newest lines first.

        Streams are labelled namespace, pod, container and app (app.kubernetes.io/name). Lines are cut to 400
        characters. Metric queries (count_over_time, rate) return series like prometheus_query.
        """
        window = parse_duration(since, maximum=MAX_WINDOW, name="since")
        clamp(limit, 1, observability.MAX_LOG_LINES, "limit")
        return await with_timeout(observability.loki_query(loki, query, window, limit), timeout, "Loki")

    @server.tool(annotations=READ_ONLY)
    async def k8s_events(
        namespace: Annotated[str, Field(description="Namespace, e.g. voting")],
        since: Annotated[str, Field(description="How far back, e.g. 30m (max 6h; Kubernetes keeps ~1h)")] = "1h",
        kind: Annotated[str | None, Field(description="Only events of this object kind, e.g. Pod, Deployment")] = None,
        name: Annotated[str | None, Field(description="Only events of the object with this name")] = None,
        limit: Annotated[int, Field(description="Maximum events (1-100)")] = 50,
    ) -> dict[str, Any]:
        """Kubernetes events in a namespace, newest first: scheduling, image pulls, probes, OOM kills, scaling."""
        check_namespace(namespace, settings.namespaces)
        window = parse_duration(since, maximum=MAX_WINDOW, name="since")
        if kind is not None and not kind.isalpha():
            check_k8s_name(kind, "kind")
        if name is not None:
            check_k8s_name(name, "name")
        clamp(limit, 1, 100, "limit")
        return await with_timeout(kube.events(namespace, window, kind, name, limit), timeout, "Kubernetes API")

    @server.tool(annotations=READ_ONLY)
    async def k8s_describe(
        kind: Annotated[Kind, Field(description="pod, deployment or statefulset")],
        namespace: Annotated[str, Field(description="Namespace, e.g. voting")],
        name: Annotated[str, Field(description="Object name")],
    ) -> dict[str, Any]:
        """A compact describe of a pod, deployment or statefulset: images, resources, env (sensitive values
        hidden), container states with last termination reason and restarts, conditions, the pods of a
        workload, and its events of the last hour. Secrets cannot be read."""
        check_namespace(namespace, settings.namespaces)
        check_k8s_name(name, "name")
        return await with_timeout(kube.describe(kind, namespace, name), timeout, "Kubernetes API")

    @server.tool(annotations=READ_ONLY)
    async def argocd_app_history(
        app: Annotated[str, Field(description="Argo CD Application, e.g. voting, data, alerts")],
        limit: Annotated[int, Field(description="Maximum history entries (1-20)")] = 10,
    ) -> dict[str, Any]:
        """Deployment history of an Argo CD Application: which Git revision was synced when, the current sync and
        health status, and the last sync operation (its phase and error message, e.g. a failed hook)."""
        check_k8s_name(app, "application")
        clamp(limit, 1, 20, "limit")
        return await with_timeout(kube.argocd_history(settings.argocd_namespace, app, limit), timeout, "Kubernetes API")

    @server.tool(annotations=READ_ONLY)
    async def gitops_log(
        since: Annotated[str, Field(description="How far back, e.g. 2h, 1d (max 14d)")] = "1d",
        path: Annotated[
            str | None,
            Field(
                description="Only commits touching this existing path, e.g. charts/voting or envs/local.yaml. "
                "Omit it unless you know the path: a wrong path just returns no commits."
            ),
        ] = None,
        max_count: Annotated[int, Field(description="Maximum commits (1-50)")] = 20,
        with_diff: Annotated[bool, Field(description="Include each commit's diff (cut to 4000 characters)")] = False,
    ) -> dict[str, Any]:
        """git log of the GitOps repository (voting-gitops, the branch the cluster follows): every change to the
        desired state of the cluster, newest first, with the files touched and optionally the diff."""
        window = parse_duration(since, maximum=timedelta(days=14), name="since")
        if path is not None:
            check_repo_path(path)
        clamp(max_count, 1, 50, "max_count")
        return await gitops.gitops_log(
            settings.gitops_repo, settings.gitops_branch, window, path, max_count, with_diff, timeout
        )

    return server


def main() -> None:
    build_server(Settings.from_env()).run("stdio")


if __name__ == "__main__":
    main()
