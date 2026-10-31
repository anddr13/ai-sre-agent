"""Read-only Kubernetes access: events, a compact describe of pods/deployments/statefulsets, Argo CD history.

Only get/list calls are made, with the agent's own ServiceAccount (see deploy/rbac.yaml). Secrets are not
readable by that account, and container env values that look sensitive are hidden on top of that.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.exceptions import ApiException
from mcp.server.mcpserver.exceptions import ToolError

from .limits import redact_env, shorten

Kind = Literal["pod", "deployment", "statefulset"]

MAX_EVENTS = 100
MAX_PODS = 15
# Annotations that only add noise (and kubectl's last-applied can carry a whole manifest).
NOISY_ANNOTATIONS = ("kubectl.kubernetes.io/last-applied-configuration",)


class Kube:
    def __init__(self, kubeconfig: str):
        self._kubeconfig = kubeconfig
        self._api: client.ApiClient | None = None

    async def api(self) -> client.ApiClient:
        if self._api is None:
            configuration = client.Configuration()
            if self._kubeconfig:
                await config.load_kube_config(
                    config_file=self._kubeconfig, client_configuration=configuration, persist_config=False
                )
            else:
                config.load_incluster_config(client_configuration=configuration)
            self._api = client.ApiClient(configuration)
        return self._api

    async def aclose(self) -> None:
        if self._api is not None:
            await self._api.close()
            self._api = None

    async def _plain(self, obj: Any) -> Any:
        return (await self.api()).sanitize_for_serialization(obj)

    # --- events --------------------------------------------------------------------------------

    async def events(
        self, namespace: str, since: timedelta, kind: str | None, name: str | None, limit: int
    ) -> dict[str, Any]:
        selectors = []
        if kind:
            selectors.append(f"involvedObject.kind={kind}")
        if name:
            selectors.append(f"involvedObject.name={name}")
        core = client.CoreV1Api(await self.api())
        try:
            listed = await core.list_namespaced_event(namespace, field_selector=",".join(selectors) or None, limit=500)
        except ApiException as exc:
            raise _api_error(exc) from exc

        cutoff = datetime.now(UTC) - since
        events = []
        for ev in listed.items:
            last = ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp
            if last is None or last < cutoff:
                continue
            events.append(
                {
                    "last_seen": last.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "type": ev.type,
                    "reason": ev.reason,
                    "object": f"{ev.involved_object.kind}/{ev.involved_object.name}",
                    "count": ev.count or 1,
                    "message": shorten(ev.message or ""),
                }
            )
        events.sort(key=lambda e: e["last_seen"], reverse=True)
        return {"namespace": namespace, "events_total": len(events), "newest_first": events[:limit]}

    # --- describe ------------------------------------------------------------------------------

    async def describe(self, kind: Kind, namespace: str, name: str) -> dict[str, Any]:
        api = await self.api()
        try:
            if kind == "pod":
                obj = await client.CoreV1Api(api).read_namespaced_pod(name, namespace)
            elif kind == "deployment":
                obj = await client.AppsV1Api(api).read_namespaced_deployment(name, namespace)
            else:
                obj = await client.AppsV1Api(api).read_namespaced_stateful_set(name, namespace)
        except ApiException as exc:
            raise _api_error(exc) from exc

        raw = await self._plain(obj)
        result: dict[str, Any] = {"kind": kind, **_metadata(raw["metadata"])}
        if kind == "pod":
            result |= _pod(raw)
        else:
            result |= _workload(raw)
            selector = raw["spec"].get("selector", {}).get("matchLabels", {})
            result["pods"] = await self._pods(namespace, selector)
        recent = await self.events(namespace, timedelta(hours=1), None, name, 10)
        result["recent_events"] = recent["newest_first"]
        return result

    async def _pods(self, namespace: str, match_labels: dict[str, str]) -> list[dict[str, Any]]:
        if not match_labels:
            return []
        selector = ",".join(f"{k}={v}" for k, v in match_labels.items())
        listed = await client.CoreV1Api(await self.api()).list_namespaced_pod(namespace, label_selector=selector)
        pods = []
        for pod in (await self._plain(listed))["items"][:MAX_PODS]:
            summary = _pod(pod)
            pods.append(
                {
                    "name": pod["metadata"]["name"],
                    "phase": summary["phase"],
                    "containers": [
                        {k: c[k] for k in ("name", "image", "ready", "restarts", "state") if k in c}
                        for c in summary["containers"]
                    ],
                }
            )
        return pods

    # --- Argo CD -------------------------------------------------------------------------------

    async def argocd_history(self, argocd_namespace: str, app: str, limit: int) -> dict[str, Any]:
        custom = client.CustomObjectsApi(await self.api())
        try:
            obj = await custom.get_namespaced_custom_object(
                "argoproj.io", "v1alpha1", argocd_namespace, "applications", app
            )
        except ApiException as exc:
            raise _api_error(exc) from exc

        status = obj.get("status", {})
        source = obj.get("spec", {}).get("source", {})
        operation = status.get("operationState", {})
        history = [
            {
                "id": h.get("id"),
                "revision": h.get("revision"),
                "deployed_at": h.get("deployedAt"),
                "started_at": h.get("deployStartedAt"),
            }
            for h in reversed(status.get("history", []))
        ]
        return {
            "application": app,
            "source": {k: source.get(k) for k in ("repoURL", "path", "chart", "targetRevision") if k in source},
            "sync": {
                "status": status.get("sync", {}).get("status"),
                "revision": status.get("sync", {}).get("revision"),
            },
            "health": status.get("health", {}).get("status"),
            "last_operation": {
                "phase": operation.get("phase"),
                "message": shorten(operation.get("message", "")),
                "revision": operation.get("syncResult", {}).get("revision")
                or operation.get("operation", {}).get("sync", {}).get("revision"),
                "started_at": operation.get("startedAt"),
                "finished_at": operation.get("finishedAt"),
            },
            "history_newest_first": history[:limit],
        }


def _api_error(exc: ApiException) -> ToolError:
    if exc.status == 404:
        return ToolError("not found")
    if exc.status == 403:
        return ToolError("forbidden for the agent's read-only ServiceAccount")
    return ToolError(f"Kubernetes API error {exc.status}: {exc.reason}")


def _metadata(meta: dict[str, Any]) -> dict[str, Any]:
    annotations = {k: shorten(v, 200) for k, v in (meta.get("annotations") or {}).items() if k not in NOISY_ANNOTATIONS}
    owners = [f"{o['kind']}/{o['name']}" for o in meta.get("ownerReferences", [])]
    return {
        "name": meta["name"],
        "namespace": meta.get("namespace"),
        "created": meta.get("creationTimestamp"),
        "labels": meta.get("labels", {}),
        "annotations": annotations,
        **({"owners": owners} if owners else {}),
    }


def _containers(spec_containers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        c["name"]: {
            "image": c.get("image"),
            "resources": c.get("resources", {}),
            "env": redact_env(c.get("env")),
            **({"args": c["args"]} if c.get("args") else {}),
        }
        for c in spec_containers
    }


def _state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state:
        return None
    (name, detail), *_ = state.items()
    keep = {k: detail[k] for k in ("reason", "exitCode", "startedAt", "finishedAt") if k in (detail or {})}
    if detail and detail.get("message"):
        keep["message"] = shorten(detail["message"], 200)
    return {name: keep}


def _pod(pod: dict[str, Any]) -> dict[str, Any]:
    spec, status = pod.get("spec", {}), pod.get("status", {})
    specs = _containers(spec.get("containers", []))
    containers = []
    for cs in status.get("containerStatuses", []):
        containers.append(
            {
                "name": cs["name"],
                **specs.get(cs["name"], {}),
                "ready": cs.get("ready"),
                "restarts": cs.get("restartCount", 0),
                "state": _state(cs.get("state")),
                "last_state": _state(cs.get("lastState")),
            }
        )
    if not containers:  # not scheduled yet: only the spec is known
        containers = [{"name": n, **s} for n, s in specs.items()]
    return {
        "phase": status.get("phase"),
        "node": spec.get("nodeName"),
        "conditions": [
            {k: c[k] for k in ("type", "status", "reason", "message") if c.get(k)} for c in status.get("conditions", [])
        ],
        "containers": containers,
    }


def _workload(obj: dict[str, Any]) -> dict[str, Any]:
    spec, status = obj.get("spec", {}), obj.get("status", {})
    template = spec.get("template", {}).get("spec", {})
    return {
        "replicas": {
            "desired": spec.get("replicas"),
            "ready": status.get("readyReplicas", 0),
            "updated": status.get("updatedReplicas", 0),
            "available": status.get("availableReplicas", 0),
        },
        "strategy": spec.get("strategy") or spec.get("updateStrategy"),
        "conditions": [
            {k: c[k] for k in ("type", "status", "reason", "message", "lastUpdateTime") if c.get(k)}
            for c in status.get("conditions", [])
        ],
        "containers": _containers(template.get("containers", [])),
        "init_containers": list(_containers(template.get("initContainers", [])).keys()),
    }
