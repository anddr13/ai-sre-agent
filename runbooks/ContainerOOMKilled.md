# ContainerOOMKilled

**Symptom.** A container in the `voting` namespace restarted in the last 10 minutes after the kernel killed it
for exceeding its memory limit (`OOMKilled`). Whatever it held in memory is gone; repeated kills turn into a
crash loop.

## What to check

1. Which pod and container: the alert labels; `kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}`.
2. Memory use against the limit before the kill: `container_memory_working_set_bytes{namespace="voting", container="<c>"}`
   vs `kube_pod_container_resource_limits{resource="memory", container="<c>"}`. A flat line hitting a low limit
   means the limit is too small; a steady climb means a leak or growing data.
3. Did the limit change recently? Compare the limit history in Prometheus, the Deployment spec, and commits in voting-gitops.
4. For Redis: how much data it holds (`tallies`, rate-limit keys) and whether `maxmemory` is set below the container limit.
5. Restarts and impact: `kube_pod_container_status_restarts_total`; for Redis, the cache is empty after a
   restart (result-api rebuilds it from PostgreSQL), and vote-api returns 5xx while Redis is down.

## Typical causes

- Memory limit lowered below the working set.
- Data or traffic growth (more keys in Redis, bigger batches).
- A memory leak in the application.

## Mitigation

- Limit was lowered: restore the previous limit (revert the change in voting-gitops).
- Real growth: raise the limit; for Redis also set `maxmemory` with an eviction policy below the container limit,
  so Redis evicts instead of being killed.
- Leak: restart as a stopgap, then fix the code.
