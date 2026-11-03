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
| [src/ai_sre_agent/](src/ai_sre_agent) | The agent: `service.py` (Alertmanager webhook), `investigator.py` (the tool-calling loop), `redact.py`, `audit.py`, `slack.py`, `cli.py` |
| [deploy/agent.yaml](deploy/agent.yaml) | The agent in the cluster (deployed by Argo CD from this repo), audit log on a PVC |
| [scripts/](scripts) | `agent-kubeconfig.sh` (a kubeconfig for that ServiceAccount), `check-rbac.sh` (`kubectl auth can-i` assertions), `agent-secret.sh` (the Secret from `.env`) |

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

## The agent

Alertmanager posts the voting alerts to `ai-sre-agent.ai-sre-agent.svc:8080/alertmanager`. The service answers at
once and investigates in the background:

1. the alert (redacted) and the six MCP tools go to an OpenAI-compatible LLM (`LLM_BASE_URL`, `LLM_MODEL`; now
   `qwen/qwen3-14b` on OpenRouter, later the vLLM from gpu-inference-platform);
2. the model calls tools through a real MCP session; every result is redacted (tokens, passwords, keys, IPs,
   e-mails) and cut to size before the model sees it, and labelled `[call N]`;
3. it answers with a JSON hypothesis: root cause, confidence, evidence as call numbers, mitigation as text;
4. evidence is kept only if it points at a call that happened, and is shown with that call's real arguments and
   result; the message goes to Slack, a resolved alert to the same thread;
5. everything (the alert, every LLM turn, every tool call and result, the outcome) is written to `audit/` as JSONL.

Limits: 12 LLM turns, 80k tokens, a timeout per tool call and per LLM call; the last turn has no tools, so the
model has to conclude. The same alert group is investigated once per hour, at most two at a time.

First end-to-end run, scenario 1 (bad deploy), 2026-10-31: the agent named the exact release commit and the missing
image tag, cited `argocd_app_history`, `gitops_log` (with the diff) and `k8s_describe`, and suggested
`git revert <sha>` on `lab`, the same as the expected answer written before the run. 2 LLM turns, 4 tool calls,
10.9k tokens, $0.0015, 75 s from the alert firing to the Slack message.

```bash
uv run ai-sre-investigate VotingPodNotStarting --slack   # one investigation by hand, from Alertmanager's API
scripts/agent-secret.sh                                  # LLM key + Slack token into the cluster
```

## Backtest

`uv run ai-sre-backtest` breaks the stand with each scenario, lets the agent investigate the real alert and scores
the answer against the cause that `break.sh` wrote down before the alert fired (regexes in `expected.yaml`: the
revision, the broker, the setting). Top-1 / top-3 are the first / any of the three hypotheses, triage is
wake / morning / noise. `--agent rules` runs the baseline without an LLM: one fixed playbook per alert over the
same MCP tools. Results: `backtest/results/<time>-<label>/`.

Runs of 2026-11-02, the same stand, 8 scenarios once each (`--no-rag` is the ablation):

| | Top-1 | Triage | Wrong but "high" | Median alert → answer | Median cost / investigation |
|---|---|---|---|---|---|
| Single agent, `qwen/qwen3-14b`, no RAG | 3/8 | 7/8 | 2/8 | 95 s | $0.0014 |
| Single agent, `qwen/qwen3-14b`, RAG top-3 runbooks | 5/8 | 7/8 | 1/8 | 117 s | $0.0022 |

RAG fixes 3 (the stopped Kafka broker) and 4 (the failover) and costs ~1.6× the tokens. Both still miss 2 (they
blame a reverted image tag or Redis, not the config change), 6 (they never look at WAL replay) and 8 (they blame
a harmless deploy; the scenario is noise). One run each: the difference is two scenarios, so it needs repeated
runs before it means anything.

The first tables (2026-11-01: LLM 6/8, rules 6/8) are not comparable: the runner then waited only for the alerts
to clear, so the previous scenario's errors were still in the logs the agent read, and scenario 6 was scored on
restating the alert. The runner now also waits for quiet logs, and scenario 6 needs the mechanism. The rules
baseline has not been rerun since.

### Investigators + verifier (`--agent team`)

Three investigators in parallel, one per class of causes (changes and config; resources and limits; Kafka,
PostgreSQL, Redis and the network), each with its own budget. Every hypothesis cites its tool calls; one that cites
no call, or only failed or empty results, is dropped in code. A verifier without tools reads the cited results
and rejects what they do not show, then ranks the rest (`team.py`). Runs of 2026-11-02/03, RAG on, scored on the
hypotheses only:

| | Top-1 | Top-3 | Wrong but "high" | Median cost / investigation |
|---|---|---|---|---|
| Single agent (above) | 5/8 | 5/8 | 1/8 | $0.0022 |
| Team, verifier `qwen/qwen3-14b` | 5/8 | 6/8 | 2/8 | $0.0057 |
| Team, verifier `qwen/qwen3-235b-a22b-2507` | 4/8 | 6/8 | 3/8 | $0.0053 |

**These team runs do not count.** The token of the agent's kubeconfig expired before the first of them, so every
`k8s_*` call returned Unauthorized: the investigators saw metrics, logs and git, but no events and no pod
descriptions. The single-agent runs above were not affected (0 failed Kubernetes calls). The backtest now checks
the agent's tools before every scenario and stops instead; the team runs are to be repeated.

## MLflow

MLflow runs in the cluster (`mlflow.localhost:8090`) on the agent's own PostgreSQL (`deploy/db.yaml`: CNPG,
pgvector; separate from voting-pg, which the scenarios break). With `MLFLOW_TRACKING_URI` set:

- a backtest is a run in the experiment `ai-sre-backtest`: agent, model, prompt version and commit as params,
  per-scenario and total scores as metrics, `summary.md` and `results.jsonl` as artifacts;
- an investigation is a trace: every LLM turn and every tool call as spans, with the redacted text the model saw;
  the agent in the cluster traces the real alerts into the experiment `ai-sre-agent`.

## Status

- [x] Stand: kind + Prometheus, Alertmanager, Grafana, Loki
- [x] voting-app on PostgreSQL, exactly-once verified with k6 while the consumers are SIGKILLed
- [x] 8 alerts + runbooks, each fired at least once
- [x] Scenarios 1-8
- [x] Read-only MCP server (Prometheus, Loki, Kubernetes, Argo CD, git history) + RBAC check
- [x] The agent: Alertmanager webhook → investigation → Slack, redaction, audit, limits
- [x] Backtest runner + rule baseline, first table
- [x] The agent's PostgreSQL (pgvector) + MLflow tracking and tracing
- [ ] RAG over the runbooks, investigators + verifier, apply-fix + time to recovery, ablations, vLLM
