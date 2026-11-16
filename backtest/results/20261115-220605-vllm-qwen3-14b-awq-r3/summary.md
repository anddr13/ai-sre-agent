# Backtest vllm-qwen3-14b-awq-r3

Model `Qwen/Qwen3-14B-AWQ`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 46.7s | 40.3s | 13050 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 46.7s | 38.9s | 13804 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → morning ❌ | high | 44.7s | 35.4s | 15747 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | medium | 47.7s | 38.1s | 14786 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 37.7s | 34.7s | 15666 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | high | 47.7s | 44.2s | 18774 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 47.7s | 37.6s | 17481 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 47.7s | 44.0s | 14199 | $0.0000 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 6/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 47.2s, median investigation 38.5s
- **Median cost**: $0.0000, total $0.0000, median tokens 15226.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 834737e61c49 | applied revert 834737e61c4970d34907d852dbc9c2e04464a365 951e2464c65c67fd4d7109c062be221ed02d1214 | ✅ | 96.7s |
| 02-config-regression #1 | revert 881cba2a8336 | applied revert 881cba2a83360c54b6a1bfd959ad075395edd06a 1960a9d051eca269ef34654da223e6d7aec9cc35 | ✅ | 373.7s |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-1 | applied restart_pod voting-dual-role-1 | ✅ | 406.7s |
| 04-postgres-failover #1 | revert 892f65cd53a1 | rejected: 892f65cd53a1 is already reverted | ✅ | 290.7s |
| 05-postgres-connections #1 | revert 8bd799877f45 | applied revert 8bd799877f45835e4782def763ccc6915b931869 d8094d3b96cfd590ea355baa6b23364dbff538f0 | ✅ | 547.7s |
| 06-replica-lag #1 | revert 8bd799877f45 | rejected: 8bd799877f45 is already reverted | ❌ | - |
| 07-redis-oom #1 | revert c0a5747a872d | applied revert c0a5747a872d91e7de6f485b18b7d5c4a957e5f6 48e0f748bd0b14cd44b57691e1a8e19302689bbe | ✅ | 348.7s |
| 08-noise #1 | revert 4bc60dbc50f3f3254b8e6046d6106c79b17aaa2e | applied revert 4bc60dbc50f3f3254b8e6046d6106c79b17aaa2e f4a7d505346e0279ec064034f0f7d8f59ddb0ca9 | ✅ | 278.7s |

- **Recovered after the agent's fix**: 7/8, median alert → recovery 348.7s
