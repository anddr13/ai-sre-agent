# ai-sre-agent

A read-only agent that investigates Kubernetes incidents: a few minutes after an alert it posts the likely
root cause, the evidence (query + result) and a suggested fix. It never changes the cluster.
A backtest on chaos scenarios with known causes measures how often it is right.

Work in progress; the full plan is in [PLAN.md](PLAN.md) (in Russian).

## The stand

The "production" it investigates is the [voting-app](https://github.com/anddr13/voting-app)
(Kafka/Strimzi, PostgreSQL on CloudNativePG, Redis, KEDA), deployed by Argo CD from the `lab` branch of
[voting-gitops](https://github.com/anddr13/voting-gitops) onto the kind cluster from
[voting-infra-local](https://github.com/anddr13/voting-infra-local), with kube-prometheus-stack, Loki and Alloy.

## What is here

| Path | What |
|------|------|
| [runbooks/](runbooks) | One runbook per alert (symptom, what to check, typical causes, mitigation); each alert's `runbook_url` points here |
| [scenarios/](scenarios) | Chaos scenarios: `break.sh`, `restore.sh`, and the expected answer written before the agent runs |
| [src/ai_sre_agent/mcp_server/](src/ai_sre_agent/mcp_server) | The read-only MCP server: the only way the agent looks at the cluster |
| [deploy/rbac.yaml](deploy/rbac.yaml) | The agent's ServiceAccount and ClusterRole (get/list/watch; no Secrets, no exec, no logs) |
| [scripts/](scripts) | `agent-kubeconfig.sh` (a kubeconfig for that ServiceAccount), `check-rbac.sh` (`kubectl auth can-i` assertions) |

The alerts themselves live in voting-gitops (`charts/alerts`); Alertmanager routes them to the agent's webhook.

## The MCP server

Six tools, official MCP Python SDK, each with fixed and validated parameters, a timeout and a bounded answer:

| Tool | What it reads |
|------|---------------|
| `prometheus_query` | PromQL, instant or range (max 6h, 30 series, 60 points each) |
| `loki_query` | LogQL, newest lines first (max 300 lines, 400 characters each) |
| `k8s_events` | events of a namespace, optionally of one object |
| `k8s_describe` | a compact describe of a pod, deployment or statefulset, sensitive env values hidden |
| `argocd_app_history` | synced revisions, sync/health status and the last operation of an Argo CD Application |
| `gitops_log` | `git log` (optionally with diffs) of the branch the cluster follows |

There is no shell and no write call anywhere; the Kubernetes tools run as the agent's own ServiceAccount, and
`scripts/check-rbac.sh` proves it cannot delete, patch, exec or read Secrets.

```bash
uv sync
scripts/agent-kubeconfig.sh            # ~/.kube/ai-sre-agent.yaml, a 24h token of the read-only ServiceAccount
scripts/check-rbac.sh                  # 30 checks, both impersonated and with that kubeconfig
uv run pytest                          # unit tests + every tool against the stand (-m integration)
uv run ai-sre-mcp                      # the server over stdio
```

Settings come from the environment or a local `.env` (never committed): `PROMETHEUS_URL`, `LOKI_URL`,
`AGENT_KUBECONFIG`, `GITOPS_REPO`, `GITOPS_BRANCH`, `TOOL_TIMEOUT_S`; the agent itself will also read
`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL`.

## Status

- [x] Stand: kind + Prometheus, Alertmanager, Grafana, Loki
- [x] voting-app on PostgreSQL, exactly-once verified with k6 while the consumers are SIGKILLed
- [x] 8 alerts + runbooks, each fired at least once
- [x] Scenarios 1, 3, 4, 5, 7
- [x] Read-only MCP server (Prometheus, Loki, Kubernetes, Argo CD, git history) + RBAC check
- [ ] The agent: Alertmanager webhook → investigation → Slack
