# VotingApiLatencyHigh

**Symptom.** The p99 response time of vote-api over the last minute is above 100 ms. The rule has no `for`
clause and a 1-minute window, so it is sensitive: it can fire on a short burst and resolve by itself.

## What to check

1. Is it still firing, and how often has it fired: `ALERTS{alertname="VotingApiLatencyHigh"}` over the last hours.
   Many short firings that resolve on their own are a sign of noise, not of an incident.
2. Is anything else wrong at the same time: 5xx (`VotingHttp5xxRate`), consumer lag, Kafka or PostgreSQL alerts.
   Latency alone, with no errors, rarely needs a human at night.
3. Latency over a longer window: p50/p95/p99 over 15 minutes from
   `traefik_service_request_duration_seconds_bucket{exported_service=~"voting-vote-api-.*"}`. A sustained rise is real;
   a single spike is not.
4. Did a deploy happen right before (Argo CD history of `voting`)? Pods starting up (cold JIT, new connections)
   cause short spikes after every rollout.
5. Request rate at the same time: a traffic burst explains a spike.

## Typical causes

- A short traffic burst or a rollout: noise, resolves by itself.
- A slow dependency (Kafka `acks=all` with a broker missing, Redis under memory pressure): real, comes with other alerts.
- CPU throttling of vote-api pods.

## Mitigation

- Spike that resolved by itself, no errors, no other alerts: no action now; consider it noise and tune the rule
  (longer window, a `for` clause) in working hours.
- Sustained latency with errors: follow the runbook of the failing dependency; scale vote-api if it is CPU-bound.
