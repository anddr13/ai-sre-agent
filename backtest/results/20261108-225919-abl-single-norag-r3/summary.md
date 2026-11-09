# Backtest abl-single-norag-r3

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 25.8s | 17.8s | 10972 | $0.0015 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ✅ | wake → wake ✅ | high | 27.8s | 27.7s | 14777 | $0.0021 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → morning ❌ | medium | 20.8s | 16.8s | 8700 | $0.0012 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | high | 61.8s | 55.3s | 8425 | $0.0012 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ❌ | ❌ | wake → morning ❌ | high | 52.8s | 48.4s | 10744 | $0.0015 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | medium | 23.8s | 17.6s | 10601 | $0.0015 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 49.8s | 47.0s | 12816 | $0.0018 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | medium | 35.8s | 30.7s | 9304 | $0.0014 |

- **Top-1**: 3/8, **top-3**: 4/8, **triage**: 5/8
- **Wrong but "high" confidence**: 3/8
- **Median alert → answer**: 31.799999999999997s, median investigation 29.2s
- **Median cost**: $0.0015, total $0.0121, median tokens 10672.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 40b8814f3863e47a52e3a8a2e742fb38485f603e | applied revert 40b8814f3863e47a52e3a8a2e742fb38485f603e 6852cad88c7333e6704e01a6917cda9686abc6cc | ✅ | 95.8s |
| 02-config-regression #1 | none | none | ❌ | - |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-1 | applied restart_pod voting-dual-role-1 | ✅ | 382.8s |
| 04-postgres-failover #1 | none | none | ✅ | 271.8s |
| 05-postgres-connections #1 | none | none | ❌ | - |
| 06-replica-lag #1 | revert 5934cbb16e4a | applied revert 5934cbb16e4aad3363081fb4da62c4d92c03b298 d9344040e2aa4cf9b22fcd6bdeca45b89cf3a554 | ❌ | - |
| 07-redis-oom #1 | revert 2f32f8b245c4 | applied revert 2f32f8b245c4f652ff51ac04f64759c6255f743e 27dd6faa1b2ce7bed8471ff78612d67c3a5d918e | ✅ | 360.8s |
| 08-noise #1 | revert 13809629015576372b45d73da59ce33dfe8f9ede | applied revert 13809629015576372b45d73da59ce33dfe8f9ede 842038f20316b852a6f9030a2d0efe04d1033c48 | ✅ | 286.8s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 286.8s
