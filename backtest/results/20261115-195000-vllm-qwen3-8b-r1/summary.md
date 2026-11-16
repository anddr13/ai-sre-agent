# Backtest vllm-qwen3-8b-r1

Model `Qwen/Qwen3-8B`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 53.4s | 51.5s | 12399 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ❌ | wake → wake ✅ | high | 38.4s | 33.2s | 4735 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | high | 68.4s | 61.9s | 12260 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 42.4s | 37.3s | 4767 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 67.4s | 61.1s | 10424 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | medium | 102.4s | 100.2s | 16263 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 84.4s | 75.5s | 17220 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | medium | 58.4s | 56.4s | 12468 | $0.0000 |

- **Top-1**: 4/8, **top-3**: 4/8, **triage**: 7/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 62.900000000000006s, median investigation 58.75s
- **Median cost**: $0.0000, total $0.0000, median tokens 12329.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert a76375be8b31 | applied revert a76375be8b31980ca98fb4fb324ca381543d84d0 31e07e19c981b7a5deeaae79b174339070b7974b | ✅ | 94.4s |
| 02-config-regression #1 | none | none | ❌ | - |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-0 | applied restart_pod voting-dual-role-0 | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 292.4s |
| 05-postgres-connections #1 | revert 0b5e7bda4cdb | applied revert 0b5e7bda4cdbd618586542c6636eb2c1d4e0f9b3 322ef888c5015c8ab8ccaa6bd041c36f379cf0ee | ✅ | 586.4s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | revert c0acc1190f12 | applied revert c0acc1190f12f97a6690c854c718dfa7dca5672d ec7a99f493d962cd711ccb9d700c8dc71c8e3278 | ✅ | 385.4s |
| 08-noise #1 | revert f870dfe151ae62929036f79a6f09765c9ee4f091 | applied revert f870dfe151ae62929036f79a6f09765c9ee4f091 72b4beae218094b383ca63e3b9688f68652f2b2d | ✅ | 289.4s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 292.4s
