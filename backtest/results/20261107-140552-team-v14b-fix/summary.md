# Backtest team-v14b-fix

Model `qwen/qwen3-14b`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → morning ❌ | high | 129.2s | 115.2s | 119255 | $0.0159 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 72.2s | 65.3s | 39986 | $0.0055 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ✅ | wake → morning ❌ | medium | 110.2s | 105.3s | 67823 | $0.0093 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 65.2s | 59.4s | 43294 | $0.0059 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 131.2s | 123.6s | 83894 | $0.0112 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → noise ❌ | low | 144.2s | 138.4s | 101135 | $0.0136 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 321.2s | 311.8s | 84980 | $0.0115 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 121.2s | 115.8s | 80352 | $0.0110 |

- **Top-1**: 5/8, **top-3**: 6/8, **triage**: 4/8
- **Wrong but "high" confidence**: 0/8
- **Median alert → answer**: 125.19999999999999s, median investigation 115.5s
- **Median cost**: $0.0111, total $0.0839, median tokens 82123.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 74aabad45047 | applied revert 74aabad450470254eed3caced8327794e7bc530a 97acb486ba30c37c61d75b77aa38ccc5011609ce | ✅ | 158.2s |
| 02-config-regression #1 | revert b25e3a9c2832 | applied revert b25e3a9c28329eb949bf9000fef7c64994d069d2 8285f458f4d1ffd0fce6dd0931e1d56b9341b6c0 | ✅ | 399.2s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 305.2s |
| 05-postgres-connections #1 | revert 7333726db309 | applied revert 7333726db3094d677161e1b1f24ff1f427efb41a 8cc60708a93d690ebf680d28ee986d1ca68f1c61 | ✅ | 641.2s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | none | none | ❌ | - |
| 08-noise #1 | revert c3f12179d1cb2fc67463cd1787502b655f477b83 | applied revert c3f12179d1cb2fc67463cd1787502b655f477b83 f55ab9b03566aaf5cf99cc16440fc4adbaf61680 | ✅ | 311.2s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 311.2s
