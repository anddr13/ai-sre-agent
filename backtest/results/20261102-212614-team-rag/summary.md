# Backtest team-rag

Model `qwen/qwen3-14b`, prompt `b4aa45d8`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 67.4s | 49.6s | 42860 | $0.0057 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 162.4s | 125.2s | 38825 | $0.0054 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ✅ | wake → wake ✅ | high | 141.4s | 104.1s | 56397 | $0.0078 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | high | 263.4s | 231.7s | 44746 | $0.0062 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → morning ✅ | medium | 282.4s | 250.0s | 81435 | $0.0109 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | medium | 273.4s | 248.1s | 29085 | $0.0040 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 210.4s | 187.5s | 38947 | $0.0052 |

- **Top-1**: 4/7, **top-3**: 5/7, **triage**: 6/7
- **Wrong but "high" confidence**: 2/7
- **Median alert → answer**: 210.4s, median investigation 187.5s
- **Median cost**: $0.0057, total $0.0453, median tokens 42860
