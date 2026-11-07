# Backtest stands on GCE

One backtest takes ~3 hours on the laptop (8 scenarios, up to 15 minutes of recovery each with `--apply-fix`).
Ablations and repeats need many of them, so they run side by side on Google Compute Engine machines, one per run.
Everything long runs in tmux on the machines, so the laptop is needed only to start the runs and to collect the
results. It may switch off in between.

Each machine runs **the same kind stand as the laptop** ([voting-infra-local](https://github.com/anddr13/voting-infra-local)).
The scenarios stay unchanged: the Kafka broker is still frozen from the kind node, k6 still runs on the kind network.
The results compare with the local ones. A managed cluster (GKE, EKS) would have been a different stand
(network disks instead of local-path, other timings), not just a bigger one.

The scenarios commit their breakages to the repository and branch the stand follows. The stands therefore follow
a copy, [voting-gitops-backtest](https://github.com/anddr13/voting-gitops-backtest) (created by the first `prepare`,
Actions off), and never touch voting-gitops itself. Stand N gets a branch of its own there, `lab-N`, copied from
`lab` of voting-gitops by `prepare`. `GITOPS_BRANCH` points the scenario scripts and the agent's `gitops_log` at it.
`GITOPS_REPO_URL` and `GITOPS_REVISION` in `voting-infra-local/scripts/up.sh` point Argo CD at it.

## What it creates

In project `voting-gke-cdzjn`, zone `europe-central2-a`:

- A network of its own. The firewall admits SSH from the laptop's IP only. The stand listens on 127.0.0.1 of
  the machine, so nothing else is open.
- `STANDS` (default 3) `e2-standard-8` machines (8 vCPU, 32 GiB, 80 GB pd-balanced) with Ubuntu 24.04 and no
  service account. They are not Spot: a reclaimed machine would lose a 3-hour run. cloud-init installs Docker, kind,
  kubectl, helm and uv at the laptop's versions. About $0.3/h per machine, so 3 stands for 4 hours is about $4.
- A deploy key with write access to the copy only (the scenarios push to `lab-N`). It is on the machines only while
  they exist. `down` deletes it, along with the `lab-N` branches. The copy itself stays.

What reaches the machines from `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `VERIFIER_MODEL`,
`MLFLOW_TRACKING_URI`. Slack stays off. Each stand has its own ai-sre-db and MLflow. `collect` brings the result
directories (`summary.md`, `results.jsonl`) back.

## Use

Run it from Git Bash in the repository root, with `gcloud auth application-default login` done. Push the ai-sre-agent
revision the stands should run first (`AGENT_REF`, default `main`).

```bash
cloud/stands.sh plan               # terraform plan into cloud/tfplan: read it
cloud/stands.sh up                 # apply that plan, wait for cloud-init (~5 min)
cloud/stands.sh prepare            # starts each stand coming up in tmux on its machine (~20 min)
cloud/stands.sh run 1 --agent team --apply-fix --label team-a      # waits for the stand, then runs
cloud/stands.sh run 2 VERIFIER_MODEL= --agent team --apply-fix --label team-b
cloud/stands.sh run all --label repeat   # the same backtest on every stand
cloud/stands.sh run 1 --no-rag --apply-fix --label team-c   # queued: runs once team-a is done
# the laptop may switch off now
cloud/stands.sh status
cloud/stands.sh collect            # backtest/results/ and audit/ of every stand into this checkout
uv run ai-sre-mlflow import        # and into the laptop's MLflow (the stands' own go away with them)
cloud/stands.sh down               # always: nothing destroys the machines on its own
cloud/stands.sh leftovers          # should print nothing
```

`KEY=value` arguments before the backtest's flags are settings for that run and win over `.env`.
`cloud/stands.sh ssh N` opens a shell on stand N. There, tmux session `prepare` brings the stand up
(`~/prepare.log`), `bt` runs the queued backtests (`~/queue`, log `~/backtest.log`) and `db` holds the agent-db
port-forward.
