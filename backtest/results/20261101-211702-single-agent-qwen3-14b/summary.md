# Backtest single-agent-qwen3-14b

Model `qwen/qwen3-14b`, prompt `7053db7f`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 42.4s | 18.4s | 10880 | $0.0014 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 37.4s | 16.7s | 10402 | $0.0014 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | medium | 98.4s | 80.8s | 8094 | $0.0012 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | medium | 61.4s | 41.5s | 7356 | $0.0011 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 45.4s | 26.3s | 10192 | $0.0015 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → morning ✅ | medium | 154.4s | 136.4s | 8969 | $0.0013 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 83.4s | 61.3s | 12610 | $0.0017 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 105.4s | 87.4s | 10534 | $0.0016 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 6/8
- **Wrong but "high" confidence**: 0/8
- **Median alert → answer**: 72.4s, median investigation 51.4s
- **Median cost**: $0.0014, total $0.0112, median tokens 10297.0
