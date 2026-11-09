# Backtest abl-single-rag-r2

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 30.9s | 29.5s | 10915 | $0.0015 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 31.9s | 26.1s | 16331 | $0.0022 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → morning ❌ | high | 34.9s | 23.5s | 15690 | $0.0021 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 28.9s | 28.3s | 13562 | $0.0019 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 28.9s | 27.2s | 11678 | $0.0016 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ✅ | wake|morning → morning ✅ | medium | 33.9s | 27.3s | 19860 | $0.0026 |
| 07-redis-oom #1 | ContainerOOMKilled | ❌ | ❌ | wake → wake ✅ | low | 90.9s | 81.4s | 109256 | $0.0139 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | high | 35.9s | 30.4s | 15536 | $0.0020 |

- **Top-1**: 5/8, **top-3**: 6/8, **triage**: 6/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 32.9s, median investigation 27.8s
- **Median cost**: $0.0021, total $0.0277, median tokens 15613.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 586bb45f8c67 | applied revert 586bb45f8c670dfcdb8cad41b982f5be28df0729 1066d836c29c6b2f4b5b700e7f4d7793bfe7d496 | ✅ | 60.9s |
| 02-config-regression #1 | revert 350a47954ce7 | applied revert 350a47954ce765d1dc81623ba5cc5e7de852ca36 2460158ebdb511f3930c5544b8641c84bc500eb2 | ✅ | 353.9s |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-1 | applied restart_pod voting-dual-role-1 | ✅ | 396.9s |
| 04-postgres-failover #1 | none | none | ✅ | 278.9s |
| 05-postgres-connections #1 | revert 7e45d3232f98 | applied revert 7e45d3232f987ca7945ebff1c759cc61914be2e0 2107c3d2582b6b65c3e1a0eb6509428566b5e2bc | ✅ | 539.9s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | none | none | ❌ | - |
| 08-noise #1 | revert 2460158ebdb5 | applied revert 2460158ebdb511f3930c5544b8641c84bc500eb2 3d40704c098f7c2b3392723574e1a3465a34d333 | ✅ | 296.9s |

- **Recovered after the agent's fix**: 6/8, median alert → recovery 325.4s
