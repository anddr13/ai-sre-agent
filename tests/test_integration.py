"""Every tool against the live kind stand, through a real MCP client session.

Needs the stand from voting-infra-local, ~/.kube/ai-sre-agent.yaml (scripts/agent-kubeconfig.sh) and a
voting-gitops clone next to this repo. Skipped when the stand does not answer: pytest -m integration
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from mcp import Client

from ai_sre_agent.config import Settings
from ai_sre_agent.mcp_server.server import build_server

pytestmark = pytest.mark.integration

SETTINGS = Settings.from_env()


def _stand_is_up() -> bool:
    try:
        httpx.get(
            f"{SETTINGS.prometheus_url}/api/v1/query",
            params={"query": "1"},
            headers={"Host": SETTINGS.http_host_header},
            timeout=3,
        ).raise_for_status()
    except httpx.HTTPError:
        return False
    return Path(SETTINGS.kubeconfig).exists()


if not _stand_is_up():
    pytest.skip("the kind stand or the agent's kubeconfig is not available", allow_module_level=True)


async def call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with Client(build_server(SETTINGS)) as client:
        result = await client.call_tool(tool, arguments)
    assert not result.is_error, result.content[0].text
    return json.loads(result.content[0].text)


async def test_prometheus_instant() -> None:
    data = await call("prometheus_query", {"query": 'up{namespace="voting"}'})
    assert data["result_type"] == "vector"
    assert data["series"]


async def test_prometheus_range() -> None:
    data = await call(
        "prometheus_query", {"query": 'sum(kube_pod_status_ready{namespace="voting"})', "lookback": "30m"}
    )
    assert data["result_type"] == "matrix"
    assert 1 < len(data["series"][0]["values"]) <= 60


async def test_loki() -> None:
    data = await call("loki_query", {"query": '{namespace="voting"}', "since": "1h", "limit": 20})
    assert 0 < data["lines_returned"] <= 20
    assert {"time", "pod", "line"} <= set(data["newest_first"][0])


async def test_k8s_events() -> None:
    data = await call("k8s_events", {"namespace": "monitoring", "since": "6h"})
    assert "newest_first" in data
    # Events expire after an hour; the stand may be quiet. The kube-state-metrics events of a restart are not
    # guaranteed either, so only the shape is checked when there is nothing.
    for event in data["newest_first"]:
        assert {"last_seen", "type", "reason", "object", "message"} <= set(event)


async def test_k8s_describe_deployment_and_its_pod() -> None:
    deployment = await call("k8s_describe", {"kind": "deployment", "namespace": "voting", "name": "vote-api"})
    assert deployment["replicas"]["desired"] >= 1
    assert "vote-api" in deployment["containers"]
    assert deployment["pods"]

    pod = await call("k8s_describe", {"kind": "pod", "namespace": "voting", "name": deployment["pods"][0]["name"]})
    assert pod["phase"] == "Running"
    worker_env = {e["name"] for c in pod["containers"] for e in c.get("env", [])}
    assert "KAFKA_BROKERS" in worker_env


async def test_k8s_describe_statefulset() -> None:
    data = await call("k8s_describe", {"kind": "statefulset", "namespace": "monitoring", "name": "loki"})
    assert data["replicas"]["ready"] >= 1


async def test_k8s_describe_hides_the_database_password() -> None:
    data = await call("k8s_describe", {"kind": "deployment", "namespace": "voting", "name": "worker"})
    env = {e["name"]: e for e in data["containers"]["worker"]["env"]}
    assert "value" not in env["PGPASSWORD"]
    assert env["PGPASSWORD"]["valueFrom"]["secretKeyRef"]["name"] == "voting-pg-app"


async def test_argocd_app_history() -> None:
    data = await call("argocd_app_history", {"app": "voting"})
    assert data["history_newest_first"]
    assert len(data["history_newest_first"][0]["revision"]) == 40
    assert data["source"]["targetRevision"] == "lab"


async def test_gitops_log() -> None:
    data = await call("gitops_log", {"since": "7d", "path": "charts/voting", "max_count": 5, "with_diff": True})
    commits = data["commits_newest_first"]
    assert 0 < len(commits) <= 5
    assert all(any(f.startswith("charts/voting") for f in c["files"]) for c in commits)
    assert "diff --git" in commits[0]["diff"]
