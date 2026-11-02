# Backtest single-agent-rag-v2

Model `qwen/qwen3-14b`, prompt `7053db7f`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 68.4s | 46.4s | 13740 | $0.0018 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ❌ | wake → wake ✅ | high | 95.4s | 70.0s | 17162 | $0.0023 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → wake ✅ | high | 137.4s | 102.7s | 16858 | $0.0022 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 211.4s | 188.0s | 11819 | $0.0017 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 97.4s | 78.0s | 16131 | $0.0022 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | medium | 183.4s | 145.7s | 16824 | $0.0022 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 87.4s | 77.6s | 16207 | $0.0021 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 145.4s | 126.7s | 19855 | $0.0026 |

- **Top-1**: 5/8, **top-3**: 5/8, **triage**: 7/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 117.4s, median investigation 90.35s
- **Median cost**: $0.0022, total $0.0171, median tokens 16515.5
