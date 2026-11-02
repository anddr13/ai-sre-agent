# Backtest single-agent-norag-v2

Model `qwen/qwen3-14b`, prompt `7053db7f`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 63.4s | 49.2s | 10750 | $0.0015 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ❌ | wake → wake ✅ | high | 43.4s | 21.5s | 15457 | $0.0021 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | medium | 36.4s | 23.3s | 8218 | $0.0011 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | high | 108.4s | 84.5s | 8156 | $0.0012 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 127.4s | 95.8s | 10532 | $0.0014 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | medium | 82.4s | 50.3s | 9222 | $0.0013 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 187.4s | 158.3s | 13415 | $0.0018 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | medium | 160.4s | 149.3s | 9189 | $0.0013 |

- **Top-1**: 3/8, **top-3**: 3/8, **triage**: 7/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 95.4s, median investigation 67.4s
- **Median cost**: $0.0014, total $0.0117, median tokens 9877.0
