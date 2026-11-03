# Backtest team-rag-verifier235b-nonempty

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `1b305b64`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ❌ | ✅ | wake → wake ✅ | high | 98.4s | 89.7s | 40275 | $0.0054 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 75.4s | 52.1s | 44436 | $0.0060 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | low | 20.4s | 5.9s | 0 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ✅ | wake → wake ✅ | high | 142.4s | 101.0s | 42429 | $0.0060 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 152.4s | 135.8s | 33801 | $0.0047 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → morning ✅ | high | 134.4s | 102.7s | 44131 | $0.0059 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 95.4s | 81.8s | 35955 | $0.0051 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 155.4s | 129.0s | 35060 | $0.0050 |

- **Top-1**: 4/8, **top-3**: 6/8, **triage**: 7/8
- **Wrong but "high" confidence**: 3/8
- **Median alert → answer**: 116.4s, median investigation 95.35s
- **Median cost**: $0.0053, total $0.0380, median tokens 38115.0
