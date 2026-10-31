# PostgresPrimaryFailover

**Symptom.** In the CloudNativePG cluster `voting-pg` an instance switched between primary and replica in the
last 5 minutes, or no instance reports itself as primary. While there is no primary, writes fail: the worker
cannot store votes (consumer lag grows), migrations fail.

## What to check

1. Which instance is primary now: `cnpg_pg_replication_in_recovery{namespace="voting"} == 0` (0 = primary),
   or the `cnpg.io/instanceRole` label of the `voting-pg-*` pods.
2. The `Cluster` resource `voting-pg`: `.status.currentPrimary`, `.status.phase`, conditions and events
   (`Failing over`, `Switchover`).
3. What happened to the old primary pod: deleted, evicted, OOMKilled, node problem (pod events, restarts).
4. Write errors in the worker logs: `{namespace="voting", app="worker"} |~ "ECONNREFUSED|terminating connection|read-only"`.
5. Recovery: is the new primary accepting writes (worker logs quiet, lag shrinking:
   `kafka_consumergroup_lag{consumergroup="vote-workers"}`)?

## Typical causes

- The primary pod was deleted or evicted, or crashed; CloudNativePG promoted the replica (failover).
- A planned switchover (operator upgrade, `kubectl cnpg promote`).
- The primary is unhealthy (disk full, OOM) and the operator failed over.

## Mitigation

- A completed failover needs no action: clients reconnect through `voting-pg-rw`, and the old primary comes back
  as a replica. Confirm writes work and lag is draining.
- No primary for long: look at the operator logs (`cnpg-system`) and the Cluster status; fix what blocks
  promotion (no healthy replica, storage).
