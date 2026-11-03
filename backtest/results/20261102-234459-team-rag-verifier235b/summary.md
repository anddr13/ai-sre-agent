# Backtest team-rag-verifier235b

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `27a3bff6`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 154.4s | 128.9s | 40107 | $0.0055 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 127.4s | 107.8s | 42594 | $0.0061 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | low | 141.4s | 120.4s | 0 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 98.4s | 86.3s | 47909 | $0.0070 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 156.4s | 133.8s | 33488 | $0.0049 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → wake ✅ | medium | 96.4s | 80.1s | 42376 | $0.0061 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 104.4s | 87.4s | 34560 | $0.0049 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 232.4s | 221.5s | 33547 | $0.0047 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 7/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 134.4s, median investigation 114.1s
- **Median cost**: $0.0052, total $0.0392, median tokens 37333.5
