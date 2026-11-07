# Backtest team-v235b-fix

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 41.0s | 35.2s | 41182 | $0.0059 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 55.0s | 49.7s | 38944 | $0.0056 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → wake ✅ | high | 42.0s | 34.9s | 38275 | $0.0054 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 64.0s | 56.9s | 40579 | $0.0059 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 53.0s | 46.4s | 40450 | $0.0059 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | high | 96.0s | 89.6s | 120575 | $0.0160 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 111.0s | 108.8s | 80512 | $0.0107 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 61.0s | 54.8s | 52326 | $0.0075 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 7/8
- **Wrong but "high" confidence**: 2/8
- **Median alert → answer**: 58.0s, median investigation 52.25s
- **Median cost**: $0.0059, total $0.0630, median tokens 40880.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert e22b1dfab552 | applied revert e22b1dfab552809451c7dd6522eccdff9942a036 7719dd443633d8d784c14255dd3c590563ae502c | ✅ | 90.0s |
| 02-config-regression #1 | revert 8d7f630e0b11 | applied revert 8d7f630e0b11e4c27ae4d8156345bdfea11673ab 1d04d92c873fa7e9a19ce53464f1e91cf077ca64 | ✅ | 382.0s |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-1 | applied restart_pod voting-dual-role-1 | ✅ | 394.0s |
| 04-postgres-failover #1 | none | none | ✅ | 275.0s |
| 05-postgres-connections #1 | revert 1001de8f3794 | applied revert 1001de8f37944f8524a9551050cd0f016dc1ad03 a89f4a9cf6040a906240a231c1066ef34fe6cd0e | ✅ | 561.0s |
| 06-replica-lag #1 | revert 1001de8f3794 | rejected: 1001de8f3794 is already reverted | ❌ | - |
| 07-redis-oom #1 | revert 44cb0e2b6268d611fbbb028b8971f79ed26b465c | applied revert 44cb0e2b6268d611fbbb028b8971f79ed26b465c 041602c4d3b4950e50353c03982b956bf8df7a3c | ✅ | 422.0s |
| 08-noise #1 | restart_pod vote-api-66c76995c4-dn28f | rejected: cannot delete pod vote-api-66c76995c4-dn28f in voting | ✅ | 282.0s |

- **Recovered after the agent's fix**: 7/8, median alert → recovery 382.0s
