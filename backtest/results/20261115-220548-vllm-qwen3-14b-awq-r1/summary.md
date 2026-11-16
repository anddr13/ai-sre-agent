# Backtest vllm-qwen3-14b-awq-r1

Model `Qwen/Qwen3-14B-AWQ`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 52.4s | 42.5s | 13430 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 63.4s | 56.2s | 14759 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | medium | 46.4s | 39.1s | 13576 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 43.4s | 40.6s | 13519 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 41.4s | 34.6s | 16139 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → wake ✅ | high | 52.4s | 44.5s | 19261 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 33.4s | 32.2s | 16930 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 37.4s | 37.0s | 17935 | $0.0000 |

- **Top-1**: 5/8, **top-3**: 5/8, **triage**: 6/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 44.9s, median investigation 39.85s
- **Median cost**: $0.0000, total $0.0000, median tokens 15449.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 771341e93d22 | applied revert 771341e93d22864a27c3578c4cf7b09189be9da0 5fc2481b78f24f56a91bd76cea2d71734de84e2e | ✅ | 92.4s |
| 02-config-regression #1 | revert bd35456ac152 | applied revert bd35456ac15272033c50862a6d3347eca26391f5 f6f40fe06cb8ce43d548a8b14ee0187b265a08b6 | ✅ | 391.4s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 273.4s |
| 05-postgres-connections #1 | revert 6c47cadcd5ab | applied revert 6c47cadcd5ab7896c251b293da1e5b0f56e11a03 31a2e10af05ff77218882b904c1698712085dabb | ✅ | 552.4s |
| 06-replica-lag #1 | revert 31a2e10af05ff77218882b904c1698712085dabb | applied revert 31a2e10af05ff77218882b904c1698712085dabb 3f753e48a0972f6e49301bc50d25c598ac339810 | ❌ | - |
| 07-redis-oom #1 | revert a7b61e2b767b | applied revert a7b61e2b767be87e048908fc8a9f9ef147c26894 c7bfaf69560aafba123214c48a94d2e2b087fe8a | ✅ | 355.4s |
| 08-noise #1 | revert f6f40fe06cb8 | applied revert f6f40fe06cb8ce43d548a8b14ee0187b265a08b6 25fe9a8d53baa4a3897b71b57372a5bcf30866b2 | ✅ | 309.4s |

- **Recovered after the agent's fix**: 6/8, median alert → recovery 332.4s
