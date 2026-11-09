# Backtest abl-team-norag-r3

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 34.7s | 29.4s | 35340 | $0.0052 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 35.7s | 34.7s | 31322 | $0.0046 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | low | 63.7s | 58.9s | 47547 | $0.0068 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | low | 83.7s | 74.5s | 65059 | $0.0092 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 96.7s | 90.5s | 87669 | $0.0121 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → wake ✅ | low | 116.7s | 114.1s | 68222 | $0.0095 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 58.7s | 57.8s | 66971 | $0.0093 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 60.7s | 55.4s | 89424 | $0.0119 |

- **Top-1**: 4/8, **top-3**: 4/8, **triage**: 7/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 62.2s, median investigation 58.349999999999994s
- **Median cost**: $0.0092, total $0.0686, median tokens 66015.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert d56011037e4354863a8dc986298822759eb4f260 | rejected: d56011037e4354863a8dc986298822759eb4f260 is not a commit of voting-gitops | ❌ | - |
| 02-config-regression #1 | revert 3d6c6be1a386 | applied revert 3d6c6be1a38677abccf67ee9da73a2850c1c7c57 8840f8abae764e22af1164b2cc4f03e7cfb2f36e | ✅ | 358.7s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 273.7s |
| 05-postgres-connections #1 | revert 8e171c34013b | applied revert 8e171c34013b078195219bfd30759280a2ac7f78 e659014c23216f64324974cda8651ad97ed6562f | ✅ | 606.7s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | revert 845cf14fc3f749e127697e14997a29c44cb33f55 | applied revert 845cf14fc3f749e127697e14997a29c44cb33f55 298699e06ff880a2709efe7e54fe8f108c5cf211 | ✅ | 369.7s |
| 08-noise #1 | restart_pod vote-api-66c76995c4-mc4gj | rejected: cannot delete pod vote-api-66c76995c4-mc4gj in voting | ✅ | 90.7s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 358.7s
