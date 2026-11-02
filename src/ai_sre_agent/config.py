"""Settings from the environment (and a local .env, which is never committed)."""

import os
from dataclasses import dataclass, fields
from pathlib import Path

from dotenv import load_dotenv

# The repo root when running from a checkout: src/ai_sre_agent/config.py -> ../../..
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # --- the MCP tools ---------------------------------------------------------------------------
    # Prometheus and Loki HTTP APIs. From the laptop both go through Grafana's datasource proxy, the stand's
    # only HTTP entry point (Traefik routes on the Host header); in the cluster they are the Services.
    prometheus_url: str = "http://localhost:8090/api/datasources/proxy/uid/prometheus"
    loki_url: str = "http://localhost:8090/api/datasources/proxy/uid/loki"
    http_host_header: str = "grafana.localhost"

    # Kubeconfig of the agent's own read-only ServiceAccount (scripts/agent-kubeconfig.sh writes it).
    # Empty: use the in-cluster ServiceAccount. Deliberately not KUBECONFIG, which may point at an admin config.
    agent_kubeconfig: str = str(Path.home() / ".kube" / "ai-sre-agent.yaml")
    # Namespaces the Kubernetes tools may look into; the RBAC is cluster-wide read, this narrows it further.
    namespaces: tuple[str, ...] = ("voting", "monitoring", "argocd", "cnpg-system", "strimzi", "keda", "traefik")
    argocd_namespace: str = "argocd"

    # A clone of voting-gitops; gitops_log reads the history of this branch.
    gitops_repo: str = str(REPO_ROOT.parent / "voting-gitops")
    gitops_branch: str = "lab"

    # Every tool call is cut off after this many seconds (inside the tool, and again around the MCP call).
    tool_timeout_s: float = 20.0

    # --- the agent -------------------------------------------------------------------------------
    # Any OpenAI-compatible endpoint: OpenRouter now, the vLLM from gpu-inference-platform later.
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "qwen/qwen3-14b"
    llm_api_key: str = ""
    llm_timeout_s: float = 120.0
    # Limits of one investigation.
    max_steps: int = 12  # LLM turns
    max_tokens: int = 80_000  # prompt + completion tokens over the whole investigation
    max_tool_result_chars: int = 6_000  # what one tool result may add to the conversation
    # "single": one agent; "team": investigators per class of causes in parallel, then a verifier (team.py).
    agent_mode: str = "single"
    # Limits of one investigator of the team; the verifier is one more LLM call without tools.
    investigator_max_steps: int = 7
    investigator_max_tokens: int = 40_000
    max_parallel_investigators: int = 3
    # Several alerts at once are investigated in parallel up to this number; the rest wait.
    max_concurrent: int = 2
    # The same firing alert group is not investigated again within this many seconds.
    dedup_ttl_s: int = 3600

    slack_bot_token: str = ""
    slack_channel: str = ""

    audit_dir: str = str(REPO_ROOT / "audit")

    # MLflow tracking and tracing; empty means off. The backtest logs to its own experiment, ai-sre-backtest.
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "ai-sre-agent"

    # RAG over the runbooks (pgvector in ai-sre-db); empty means off.
    rag_database_url: str = ""
    rag_top_k: int = 3
    embedding_cache_dir: str = str(REPO_ROOT / ".cache" / "fastembed")

    @classmethod
    def from_env(cls, env_file: Path | None = REPO_ROOT / ".env") -> "Settings":
        """Every field can be set as an upper-case environment variable of the same name."""
        if env_file is not None and env_file.exists():
            load_dotenv(env_file, override=False)
        values: dict[str, object] = {}
        for f in fields(cls):
            raw = os.environ.get(f.name.upper())
            if raw is None:
                continue
            if f.type is int:
                values[f.name] = int(raw)
            elif f.type is float:
                values[f.name] = float(raw)
            elif f.type == tuple[str, ...]:
                values[f.name] = tuple(item.strip() for item in raw.split(",") if item.strip())
            else:
                values[f.name] = raw.rstrip("/") if f.name.endswith("_url") else raw
        return cls(**values)  # type: ignore[arg-type]
