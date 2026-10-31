# VotingHttp5xxRate

**Symptom.** More than 5% of the requests that Traefik routes to a voting service (`vote-api`, `result-api`)
have returned 5xx for 2 minutes. Users see failed votes or an empty results page.

## What to check

1. Which service and how bad: `sum by (service, code) (rate(traefik_service_requests_total{service=~"voting-.*"}[5m]))`.
2. When it started, and whether it lines up with a deploy: Argo CD history of `voting`, `git log` of voting-gitops.
   5xx starting right after a sync points at the new version or its configuration.
3. Logs of the failing service: `{namespace="voting", app="vote-api"} |= "error"` (or `result-api`).
   The first error after the deploy usually names the cause.
4. Diff of the new revision against the previous one: image tag, env variables, resources.
5. Dependencies: are Kafka (vote-api), Redis (both) and PostgreSQL (result-api) healthy? Check their alerts.
6. `502`/`503` from Traefik itself means no ready endpoints: are the pods Ready?

## Typical causes

- A regression in the new version, or a wrong env variable in its configuration (broker address, Redis URL, ...).
- A dependency is down or refuses writes: Kafka without enough in-sync replicas, Redis out of memory,
  PostgreSQL without a primary.
- All pods not ready (crash loop, failing readiness probe).

## Mitigation

- 5xx started with a deploy: roll back `voting` to the previous revision (git revert in voting-gitops or
  Argo CD rollback), then investigate the change.
- Dependency failure: follow that dependency's runbook; the service recovers when it is back.
