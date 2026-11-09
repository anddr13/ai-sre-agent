# Backtest abl-team-rag-r1

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 79.7s | 79.2s | 132679 | $0.0178 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 49.7s | 40.5s | 43652 | $0.0062 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | high | 53.7s | 45.1s | 56431 | $0.0077 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 49.7s | 40.2s | 40548 | $0.0059 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | medium | 98.7s | 95.5s | 94175 | $0.0127 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ✅ | wake|morning → wake ✅ | high | 127.7s | 123.8s | 105062 | $0.0141 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 100.7s | 100.0s | 74334 | $0.0103 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 50.7s | 44.2s | 51371 | $0.0073 |

- **Top-1**: 5/8, **top-3**: 6/8, **triage**: 6/8
- **Wrong but "high" confidence**: 3/8
- **Median alert → answer**: 66.7s, median investigation 62.150000000000006s
- **Median cost**: $0.0090, total $0.0819, median tokens 65382.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert afb7e2d145ec | applied revert afb7e2d145ec331d67ce0feea1cc29a950198f4a 159becc1fc965c310b271836a536422a8858de43 | ✅ | 119.7s |
| 02-config-regression #1 | revert 7aaab35a56aa | applied revert 7aaab35a56aa2c947b1c096d1a22200a8ce32dcb 279c18b028cb3d02ca31d8c5335521d688cef90c | ✅ | 371.7s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 270.7s |
| 05-postgres-connections #1 | restart_pod voting-pg-2 | applied restart_pod voting-pg-2 | ❌ | - |
| 06-replica-lag #1 | revert 250c3cde415c | rejected: 250c3cde415c is already reverted | ❌ | - |
| 07-redis-oom #1 | revert 4055ff03293e | applied revert 4055ff03293ea74ce760ef88501d5c371a5658d6 c30ab73a8f209405899187fb0be756c8e3ebda3e | ✅ | 401.7s |
| 08-noise #1 | revert 279c18b028cb3d02ca31d8c5335521d688cef90c | applied revert 279c18b028cb3d02ca31d8c5335521d688cef90c 164c7772fb80061083624de9f50a8243db77e4c1 | ✅ | 306.7s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 306.7s
