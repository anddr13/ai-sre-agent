# Backtest stands on EC2

One backtest takes ~3 hours on the laptop (8 scenarios, up to 15 minutes of recovery each with `--apply-fix`).
Ablations and repeats need many of them, so they run side by side on EC2 machines, one per run.

Each machine runs **the same kind stand as the laptop** ([voting-infra-local](https://github.com/anddr13/voting-infra-local)):
the scenarios stay unchanged (the Kafka broker is still frozen from the kind node, k6 still runs on the kind network),
and the results compare with the local ones. EKS would have been a different stand (EBS instead of local-path,
other timings), not just a bigger one.

The scenarios commit their breakages to the branch the stand follows, so stand N gets a branch of its own, `lab-N`,
copied from `lab` by `prepare`. `GITOPS_BRANCH` points the scenario scripts and the agent's `gitops_log` at it,
and `GITOPS_REVISION` in `voting-infra-local/scripts/up.sh` points Argo CD at it.

## What it creates

- A VPC with one public subnet, no NAT gateway. The security group admits SSH from the laptop's IP only.
  The stand listens on 127.0.0.1 of the machine, so nothing else is open.
- `STANDS` (default 3) On-Demand `m6i.2xlarge` (8 vCPU, 32 GiB, 80 GB gp3) with Ubuntu 24.04. cloud-init installs
  Docker, kind, kubectl, helm and uv at the laptop's versions. On-Demand because this account's organization denies
  Spot. Roughly $0.4/h per machine, so 3 stands for 4 hours is about $5.
- A deploy key with write access to voting-gitops (the scenarios push to `lab-N`). It is on the machines only while
  they exist. `down` deletes it, along with the `lab-N` branches.

What reaches the machines from `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `VERIFIER_MODEL`,
`MLFLOW_TRACKING_URI`. Slack stays off. Each stand has its own ai-sre-db and MLflow; `collect` brings the result
directories (`summary.md`, `results.jsonl`) back.

## Use

From WSL, in the repository root, with `aws login --remote --profile gpu-lab` done (Terraform uses the
`gpu-lab-terraform` profile, like voting-infra-aws). Push the ai-sre-agent revision the stands should run first
(`AGENT_REF`, default `main`).

```bash
cloud/stands.sh up                 # plan, asks before apply, waits for cloud-init (~5 min)
cloud/stands.sh prepare            # all stands in parallel (~20 min), logs in cloud/logs/prepare-N.log
cloud/stands.sh run 1 --agent team --apply-fix --label team-a
cloud/stands.sh run 2 --agent team --apply-fix --label team-b
cloud/stands.sh run all --label repeat   # the same backtest on every stand
cloud/stands.sh status
cloud/stands.sh collect            # backtest/results/ and audit/ of every stand into this checkout
cloud/stands.sh down               # always: there is no nightly destroy
cloud/stands.sh leftovers          # should print nothing
```

`cloud/stands.sh ssh N` opens a shell on stand N; the backtest runs in tmux session `bt`, its log is
`~/backtest.log`, the agent-db port-forward is in tmux session `db`. Settings for one run go before the backtest's
flags and win over `.env`: `cloud/stands.sh run 2 VERIFIER_MODEL= --agent team --label team-v14b`.
