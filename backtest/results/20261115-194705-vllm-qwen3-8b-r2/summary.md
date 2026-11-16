# Backtest vllm-qwen3-8b-r2

Model `Qwen/Qwen3-8B`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 71.1s | 64.3s | 12654 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ❌ | wake → wake ✅ | high | 37.1s | 30.8s | 4713 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ✅ | wake → wake ✅ | high | 59.1s | 58.2s | 14494 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 39.1s | 34.1s | 4770 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 73.1s | 70.3s | 13132 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | medium | 93.1s | 84.1s | 19140 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 67.1s | 60.3s | 16681 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 65.1s | 59.9s | 12672 | $0.0000 |

- **Top-1**: 4/8, **top-3**: 5/8, **triage**: 7/8
- **Wrong but "high" confidence**: 3/8
- **Median alert → answer**: 66.1s, median investigation 60.099999999999994s
- **Median cost**: $0.0000, total $0.0000, median tokens 12902.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 93de6d04deb8 | applied revert 93de6d04deb8c4a5ca9c9b7c85a409dd89c2c503 d82930acf069c3be0302805638fca233d2f334cf | ✅ | 121.1s |
| 02-config-regression #1 | none | none | ❌ | - |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 270.1s |
| 05-postgres-connections #1 | revert cee90dc9864c | applied revert cee90dc9864cdd3c826c16da8a8941e5dd861d86 f0eaaa0f19ab323f487c2b083b42759ab1b76152 | ✅ | 583.1s |
| 06-replica-lag #1 | revert f0eaaa0f19ab | applied revert f0eaaa0f19ab323f487c2b083b42759ab1b76152 e8823c50960cf12249b1bae93051e848b1fb693f | ❌ | - |
| 07-redis-oom #1 | revert 6490f71230b0 | applied revert 6490f71230b08999c89963b2930541b8cee1e389 3d9b07bec2c61af8ffd56d805ff1ea1eb6af3ebd | ✅ | 378.1s |
| 08-noise #1 | restart_pod vote-api-66c76995c4-k2nfl | rejected: cannot delete pod vote-api-66c76995c4-k2nfl in voting | ✅ | 306.1s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 306.1s
