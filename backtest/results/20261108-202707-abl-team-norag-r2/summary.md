# Backtest abl-team-norag-r2

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 120.9s | 111.7s | 33926 | $0.0051 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ✅ | wake → wake ✅ | high | 50.9s | 51.2s | 37686 | $0.0054 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → wake ✅ | high | 81.9s | 79.0s | 61987 | $0.0088 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | low | 75.9s | 68.6s | 57295 | $0.0082 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 56.9s | 48.4s | 28669 | $0.0044 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → wake ✅ | low | 90.9s | 86.5s | 91019 | $0.0127 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 77.9s | 72.9s | 77861 | $0.0106 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 60.9s | 55.8s | 41899 | $0.0061 |

- **Top-1**: 4/8, **top-3**: 5/8, **triage**: 7/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 76.9s, median investigation 70.75s
- **Median cost**: $0.0071, total $0.0613, median tokens 49597.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert e9ab4b870ccf | applied revert e9ab4b870ccf7b5d4665aefeeae23980389cfe4c fb349436848e8fc0b1ee0c3a9cfe705ccf222c50 | ✅ | 149.9s |
| 02-config-regression #1 | none | none | ❌ | - |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-1 | applied restart_pod voting-dual-role-1 | ✅ | 443.9s |
| 04-postgres-failover #1 | none | none | ✅ | 295.9s |
| 05-postgres-connections #1 | revert 358b5b7c95f0d622fb36f31d23d91ab96b8b21bb | applied revert 358b5b7c95f0d622fb36f31d23d91ab96b8b21bb 139ad8c9759f9cd66722d0746466f71da1fdf53e | ✅ | 558.9s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | revert 18fc6c2a170b | applied revert 18fc6c2a170b3a71d910cc4bb3855816d4e84041 b7ef00c37bc7daefa186296ed533a6074154d70a | ✅ | 379.9s |
| 08-noise #1 | revert 291da9c49f7f | applied revert 291da9c49f7fcbf77fe0a1ed165da1939f8872e8 fafadaba898b45a4a937bef39d4d0be5471aa0cb | ✅ | 311.9s |

- **Recovered after the agent's fix**: 6/8, median alert → recovery 345.9s
