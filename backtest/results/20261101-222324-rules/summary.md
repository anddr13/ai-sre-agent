# Backtest rules

Model `rules`, prompt `rules-v1`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | medium | 19.4s | 1.8s | 0 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | medium | 28.4s | 1.1s | 0 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | medium | 21.4s | 0.4s | 0 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | medium | 19.4s | 0.8s | 0 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | medium | 19.4s | 1.3s | 0 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → morning ✅ | medium | 18.4s | 0.4s | 0 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | medium | 22.4s | 0.8s | 0 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 15.4s | 0.0s | 0 | $0.0000 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 7/8
- **Wrong but "high" confidence**: 0/8
- **Median alert → answer**: 19.4s, median investigation 0.8s
- **Median cost**: $0.0000, total $0.0000, median tokens 0.0
