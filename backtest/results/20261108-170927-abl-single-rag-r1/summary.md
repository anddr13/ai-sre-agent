# Backtest abl-single-rag-r1

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 26.8s | 19.0s | 12301 | $0.0016 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 27.8s | 26.2s | 12774 | $0.0018 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | high | 21.8s | 19.4s | 14818 | $0.0019 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 32.8s | 25.3s | 10601 | $0.0015 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ❌ | ❌ | wake → wake ✅ | medium | 37.8s | 31.9s | 15611 | $0.0021 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | high | 25.8s | 25.0s | 17546 | $0.0023 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 23.8s | 19.6s | 18000 | $0.0023 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 42.8s | 33.4s | 16793 | $0.0023 |

- **Top-1**: 4/8, **top-3**: 4/8, **triage**: 7/8
- **Wrong but "high" confidence**: 3/8
- **Median alert → answer**: 27.3s, median investigation 25.15s
- **Median cost**: $0.0020, total $0.0158, median tokens 15214.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 2941c8bdefba | applied revert 2941c8bdefba96a6f5ed6fec27672587c429f6fc 8e5266edbc8437861bb6db9bc45cd8f6abeaaec2 | ✅ | 96.8s |
| 02-config-regression #1 | revert 585a096521c4 | applied revert 585a096521c4283ef23894d437c5a6b7a0c171ad b89a27228166478e0761e2727601c29516c54432 | ✅ | 355.8s |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-0 | applied restart_pod voting-dual-role-0 | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 283.8s |
| 05-postgres-connections #1 | restart_pod voting-pg-2 | applied restart_pod voting-pg-2 | ❌ | - |
| 06-replica-lag #1 | revert 2f581ee3a241 | applied revert 2f581ee3a2419f337238a17504a8c38b9c03baab 274af641a48da25f68b005714cab0f07612d9efc | ❌ | - |
| 07-redis-oom #1 | revert ce67b29fc9f0 | applied revert ce67b29fc9f0ab6b6f84048ed541b7ab4dff3f7a 3d88c5c842fd4c75434b9411a6fa13941310766a | ✅ | 334.8s |
| 08-noise #1 | revert 8e5266edbc84 | applied revert 8e5266edbc8437861bb6db9bc45cd8f6abeaaec2 ced9a9eadd2ba7b75220767b187b2823fede0fda | ✅ | 651.8s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 334.8s
