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

The alerts themselves live in voting-gitops (`charts/alerts`); Alertmanager routes them to the agent's webhook.

## Status

- [x] Stand: kind + Prometheus, Alertmanager, Grafana, Loki
- [x] voting-app on PostgreSQL, exactly-once verified with k6 while the consumers are SIGKILLed
- [x] 8 alerts + runbooks, each fired at least once
- [x] Scenarios 1, 3, 4, 5, 7
- [ ] Read-only MCP server (Prometheus, Loki, Kubernetes, Argo CD, git history)
- [ ] The agent: Alertmanager webhook → investigation → Slack
