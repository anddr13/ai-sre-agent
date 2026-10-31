# Chaos scenarios

Each scenario breaks the kind stand from [voting-infra-local](https://github.com/anddr13/voting-infra-local)
in one known way, waits for its alert, and puts everything back:

```bash
scenarios/01-bad-deploy/break.sh     # breaks, writes the expected answer, waits for the alert
scenarios/01-bad-deploy/restore.sh   # undoes it, waits for the alert to clear
```

| # | Scenario | How it breaks | Alert |
|---|----------|---------------|-------|
| 1 | `01-bad-deploy` | release commit in voting-gitops `lab` with an image tag that does not exist | `VotingPodNotStarting` |
| 3 | `03-kafka-broker-down` | SIGSTOP of one broker's JVM under load (see below) | `KafkaUnderReplicatedPartitions` |
| 4 | `04-postgres-failover` | deletes the PostgreSQL primary pod under load | `PostgresPrimaryFailover` |
| 5 | `05-postgres-connections` | commit lowering `max_connections` to 8, under load | `PostgresConnectionsHigh` |
| 7 | `07-redis-oom` | commit lowering the Redis memory request and limit to 10Mi, under load | `ContainerOOMKilled` |

Scenarios 2, 6 and 8 come in week 2 (see [PLAN.md](../PLAN.md)).

## Rules

- **The answer is written before the agent can look.** `expected.yaml` is the template; `break.sh` fills in
  the facts of the run (revision, pod) and saves it in `.state/<scenario>.expected.yaml` before the alert fires.
- **Changes go through Git, rollbacks too.** Breakages that are configuration changes are commits on the
  `lab` branch of voting-gitops; `restore.sh` makes a `git revert` (never a reset or force push), so the
  history the agent reads shows a real deploy followed by a rollback.
- **No waiting for Argo CD's 3-minute poll.** After a push the scripts hard-refresh the Application, so the
  timing measures the agent, not Argo CD.
- **These scripts have write access, the agent does not.** They use the kind admin kubeconfig and push to
  voting-gitops; the agent only gets its read-only ServiceAccount.
- **Load** is `load.js` (k6) in a background container on the kind Docker network.

## Notes

- **Scenario 3** freezes the broker instead of deleting its pod: a deleted broker is recreated by Strimzi and
  back in sync within ~30 s, before any alert with a sensible `for` fires. A frozen JVM still passes Strimzi's
  liveness probe (it only checks that a java process exists), so the pod stays Running and Ready while the
  broker is out of every ISR, like a hung broker.
- **Scenario 5**: CloudNativePG's metrics exporter connects as an ordinary role, so when the clients take every
  connection it is locked out first, and the primary's metrics disappear. `PostgresConnectionsHigh` therefore
  also fires when the exporter is up but cannot query its instance.
- Requirements: the stand from voting-infra-local, `kubectl`, `docker`, `git` with push access to voting-gitops,
  and voting-gitops checked out next to this repo on the `lab` branch (or `GITOPS_DIR`).
