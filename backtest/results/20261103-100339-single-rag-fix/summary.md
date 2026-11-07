# Backtest single-rag-fix

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 50.4s | 35.6s | 13634 | $0.0018 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 80.4s | 45.0s | 17277 | $0.0022 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | high | 114.4s | 86.7s | 14738 | $0.0020 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | low | 262.4s | 230.1s | 4431 | $0.0006 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ❌ | ❌ | wake → morning ❌ | medium | 188.4s | 151.6s | 15798 | $0.0021 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | high | 159.4s | 134.6s | 19640 | $0.0025 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 49.4s | 30.7s | 14812 | $0.0020 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 153.4s | 121.7s | 14987 | $0.0020 |

- **Top-1**: 3/8, **top-3**: 3/8, **triage**: 5/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 133.9s, median investigation 104.2s
- **Median cost**: $0.0020, total $0.0153, median tokens 14899.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 32e6e6597dcc | applied revert 32e6e6597dcc45a359f0118b5b131141eed420fd b203579b10138fcc0504c5d2de6a1a6cbdfaf323 | ✅ | 102.4s |
| 02-config-regression #1 | revert 64ba95262badc6257ea329a75d862b4599a72e60 | applied revert 64ba95262badc6257ea329a75d862b4599a72e60 41e569db1133f40ef7b330cf15ecb32cec1ae91a | ✅ | 818.4s |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-2 | applied restart_pod voting-dual-role-2 | ❌ | - |
| 04-postgres-failover #1 | none | none | ❌ | - |
| 05-postgres-connections #1 | none | none | ❌ | - |
| 06-replica-lag #1 | restart_pod voting-pg-1 | applied restart_pod voting-pg-1 | ✅ | 662.4s |
| 07-redis-oom #1 | revert e8e6dc4d024c | applied revert e8e6dc4d024c41ac68e68c3b73b800b10f8e86f6 3bda74a937e963f25050c0d2a88a810bbffe0cfc | ✅ | 488.4s |
| 08-noise #1 | revert e2425a1340bd48124b2131366bcf35f908af4b81 | applied revert e2425a1340bd48124b2131366bcf35f908af4b81 38a2c7accfe22ee3ce7c84b8d8d7f6526a3b57c2 | ✅ | 472.4s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 488.4s
