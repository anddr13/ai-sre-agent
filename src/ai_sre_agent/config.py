"""Settings from the environment (and a local .env, which is never committed)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# The repo root when running from a checkout: src/ai_sre_agent/config.py -> ../../..
REPO_ROOT = Path(__file__).resolve().parents[2]


def _list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    # Prometheus and Loki HTTP APIs. On the kind stand both go through Grafana's datasource proxy, the stand's
    # only HTTP entry point (Traefik routes on the Host header); in the cluster they would be the Services.
    prometheus_url: str = "http://localhost:8090/api/datasources/proxy/uid/prometheus"
    loki_url: str = "http://localhost:8090/api/datasources/proxy/uid/loki"
    http_host_header: str = "grafana.localhost"

    # Kubeconfig of the agent's own read-only ServiceAccount (scripts/agent-kubeconfig.sh writes it).
    # Empty: use the in-cluster ServiceAccount.
    kubeconfig: str = str(Path.home() / ".kube" / "ai-sre-agent.yaml")
    # Namespaces the Kubernetes tools may look into; the RBAC is cluster-wide read, this narrows it further.
    namespaces: tuple[str, ...] = (
        "voting",
        "monitoring",
        "argocd",
        "cnpg-system",
        "strimzi",
        "keda",
        "traefik",
    )
    argocd_namespace: str = "argocd"

    # A clone of voting-gitops; gitops_log reads the history of this branch.
    gitops_repo: str = str(REPO_ROOT.parent / "voting-gitops")
    gitops_branch: str = "lab"

    # Every tool call is cut off after this many seconds.
    tool_timeout_s: float = 20.0

    @classmethod
    def from_env(cls, env_file: Path | None = REPO_ROOT / ".env") -> "Settings":
        if env_file is not None and env_file.exists():
            load_dotenv(env_file, override=False)
        env = os.environ
        defaults = cls()
        return cls(
            prometheus_url=env.get("PROMETHEUS_URL", defaults.prometheus_url).rstrip("/"),
            loki_url=env.get("LOKI_URL", defaults.loki_url).rstrip("/"),
            http_host_header=env.get("HTTP_HOST_HEADER", defaults.http_host_header),
            kubeconfig=env.get("AGENT_KUBECONFIG", defaults.kubeconfig),
            namespaces=_list(env["K8S_NAMESPACES"]) if "K8S_NAMESPACES" in env else defaults.namespaces,
            argocd_namespace=env.get("ARGOCD_NAMESPACE", defaults.argocd_namespace),
            gitops_repo=env.get("GITOPS_REPO", defaults.gitops_repo),
            gitops_branch=env.get("GITOPS_BRANCH", defaults.gitops_branch),
            tool_timeout_s=float(env.get("TOOL_TIMEOUT_S", defaults.tool_timeout_s)),
        )
