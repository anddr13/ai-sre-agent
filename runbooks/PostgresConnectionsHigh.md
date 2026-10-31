# PostgresConnectionsHigh

**Symptom.** More than 80% of `max_connections` on an instance of `voting-pg` are in use. Above 100%
new connections fail with `FATAL: sorry, too many clients already` / `too many connections`, and the services
that need a new connection return 5xx or stop processing.

## What to check

1. Usage per instance: `cnpg_backends_total{namespace="voting"}` vs
   `cnpg_pg_settings_setting{namespace="voting", name="max_connections"}`.
2. Was `max_connections` changed recently? Compare the current setting with its history in Prometheus, and look at
   the `postgresql.parameters` of the `Cluster` resource and recent commits in voting-gitops.
3. Who holds the connections: `cnpg_backends_total` by `usename` / `datname` / `state`; many `idle` connections
   point at a client pool that is too large or leaking.
4. Did the number of clients grow: worker replicas (KEDA scales it up to 6) × `PG_POOL_MAX`, result-api replicas × its pool.
5. Errors in the logs: `{namespace="voting"} |~ "too many (clients|connections)"`.

## Typical causes

- `max_connections` lowered below what the clients need.
- More client pods than planned (autoscaling) times the pool size per pod.
- A connection leak in the application, or long idle transactions.

## Mitigation

- `max_connections` was lowered: restore the previous value (revert the change in voting-gitops).
- Too many clients: lower the pool size per pod (`PG_POOL_MAX`) or cap the replicas; long term, a pooler
  (CloudNativePG `Pooler`, PgBouncer) in front of the cluster.
- A leak: restart the leaking pods as a stopgap, then fix the code.
