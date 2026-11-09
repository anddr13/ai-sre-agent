# Backtest abl-team-rag-r3

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 129.9s | 122.4s | 139840 | $0.0188 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 99.9s | 99.5s | 101841 | $0.0137 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | medium | 54.9s | 50.1s | 73359 | $0.0098 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | medium | 77.9s | 77.2s | 140576 | $0.0183 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 96.9s | 95.8s | 96846 | $0.0128 |
| 06-replica-lag #1 | PostgresReplicationLag | ✅ | ✅ | wake|morning → wake ✅ | high | 69.9s | 66.6s | 57704 | $0.0081 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 61.9s | 58.6s | 107051 | $0.0143 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 60.9s | 58.1s | 52998 | $0.0077 |

- **Top-1**: 5/8, **top-3**: 5/8, **triage**: 7/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 73.9s, median investigation 71.9s
- **Median cost**: $0.0133, total $0.1035, median tokens 99343.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert e9446e8ad873480fdae3651a830d8c8ce27609ce | applied revert e9446e8ad873480fdae3651a830d8c8ce27609ce 158403f81503fb88a2b2fa8b446a333fd2f7aec4 | ❌ | - |
| 02-config-regression #1 | revert d9d1fb811d5b | applied revert d9d1fb811d5bba1a2f48666490733b58424edf86 1b47875ebb37d7d3b6662f3b38425b36ec40df09 | ✅ | 427.9s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 277.9s |
| 05-postgres-connections #1 | revert c45875b1e0792aff2d9a9748d38ca829c71f003f | applied revert c45875b1e0792aff2d9a9748d38ca829c71f003f 1229bfa4ac7b8999acdcfca8d6652811b0b41565 | ✅ | 607.9s |
| 06-replica-lag #1 | revert 1229bfa4ac7b | applied revert 1229bfa4ac7b8999acdcfca8d6652811b0b41565 ea84e81fc18790d097f9fbf5821973acc2eb95a8 | ❌ | - |
| 07-redis-oom #1 | revert 613268bcdd78d4fc22ef8243e9f2afe53b634c2b | applied revert 613268bcdd78d4fc22ef8243e9f2afe53b634c2b b8b63d853ad0221eb07f7a05977e0385a85d9994 | ✅ | 367.9s |
| 08-noise #1 | revert b627012df1d13b0a736a3138f637d7749b0a4d38 | applied revert b627012df1d13b0a736a3138f637d7749b0a4d38 7bc4abfba0931318e9b1fb90bf4a866ffd5590d7 | ✅ | 301.9s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 367.9s
