# Backtest vllm-qwen3-14b-awq-r2

Model `Qwen/Qwen3-14B-AWQ`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 45.1s | 36.5s | 12635 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 55.1s | 48.8s | 16477 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | medium | 46.1s | 36.4s | 14180 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 35.1s | 33.9s | 13254 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | medium | 53.1s | 44.0s | 15745 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ✅ | wake|morning → wake ✅ | high | 45.1s | 44.2s | 17737 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 47.1s | 37.6s | 17422 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 42.1s | 39.1s | 15810 | $0.0000 |

- **Top-1**: 5/8, **top-3**: 6/8, **triage**: 6/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 45.6s, median investigation 38.35s
- **Median cost**: $0.0000, total $0.0000, median tokens 15777.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 58f4da62115d | applied revert 58f4da62115dbd6515a4c7c03849b2bd1046b93f dfe91f32a1d24533f8ed114748ac445fd9f97911 | ✅ | 95.1s |
| 02-config-regression #1 | revert dfe91f32a1d2 | applied revert dfe91f32a1d24533f8ed114748ac445fd9f97911 3f96bdb5d32cdc73d655653591238e320e3a78f9 | ✅ | 1335.1s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 276.1s |
| 05-postgres-connections #1 | revert 13e3b38c1bda969b4e1a5c70e9e52c8e10b95bf2 | applied revert 13e3b38c1bda969b4e1a5c70e9e52c8e10b95bf2 00eb1eb452ec15f90221945123d46f62720ef8dc | ✅ | 565.1s |
| 06-replica-lag #1 | revert 00eb1eb452ec | applied revert 00eb1eb452ec15f90221945123d46f62720ef8dc 111664180a327951c71046eceed317217ce80aee | ❌ | - |
| 07-redis-oom #1 | revert 2968470637eb | applied revert 2968470637eb2125167b9277ccebad851186461f 3fc0c7010931e6488678cc680a7a62fda4e6caa6 | ✅ | 349.1s |
| 08-noise #1 | revert dc8aa19924b380f135ee06bfcd8c77459aa1c941 | applied revert dc8aa19924b380f135ee06bfcd8c77459aa1c941 ba030ed884867d2f5319b37159900a4fbf91252e | ✅ | 304.1s |

- **Recovered after the agent's fix**: 6/8, median alert → recovery 326.6s
