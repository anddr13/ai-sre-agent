# Backtest single-agent-rag

Model `qwen/qwen3-14b`, prompt `7053db7f`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 152.4s | 140.2s | 15540 | $0.0021 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 92.4s | 81.0s | 13898 | $0.0019 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → morning ❌ | high | 60.4s | 48.1s | 14474 | $0.0019 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 200.4s | 191.9s | 14968 | $0.0020 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 91.4s | 78.6s | 13180 | $0.0018 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → morning ✅ | high | 74.4s | 60.2s | 17437 | $0.0023 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 28.4s | 26.3s | 17474 | $0.0023 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | medium | 33.4s | 24.3s | 19941 | $0.0026 |

- **Top-1**: 7/8, **top-3**: 7/8, **triage**: 6/8
- **Wrong but "high" confidence**: 0/8
- **Median alert → answer**: 82.9s, median investigation 69.4s
- **Median cost**: $0.0020, total $0.0168, median tokens 15254.0
