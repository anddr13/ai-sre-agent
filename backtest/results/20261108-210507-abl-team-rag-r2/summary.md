# Backtest abl-team-rag-r2

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 83.8s | 76.1s | 91143 | $0.0123 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 126.8s | 120.6s | 78732 | $0.0109 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → wake ✅ | high | 78.8s | 69.0s | 88975 | $0.0119 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 122.8s | 117.9s | 86654 | $0.0119 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 42.8s | 36.8s | 43281 | $0.0063 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | low | 81.8s | 72.7s | 115691 | $0.0154 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 83.8s | 77.8s | 43580 | $0.0061 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 139.8s | 129.6s | 90872 | $0.0125 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 7/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 83.8s, median investigation 76.94999999999999s
- **Median cost**: $0.0119, total $0.0874, median tokens 87814.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert f194e5d2e17b12fd12b5b316c65b1efc0e5f450e | rejected: f194e5d2e17b12fd12b5b316c65b1efc0e5f450e is not a commit of voting-gitops | ❌ | - |
| 02-config-regression #1 | revert e02f2869afa0 | applied revert e02f2869afa03ca01ac203d351f6d9ce180a15b9 60b835f6f8104c9512405865cb0a5d7599a19c83 | ✅ | 453.8s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 282.8s |
| 05-postgres-connections #1 | revert 765256212af0 | applied revert 765256212af001dbe8da78e96227c00425039b63 a3f6e0b4eff4253306675b9acc8cb57764828dd8 | ✅ | 552.8s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | revert ea93902f9ba0255e1c7b5cc821fe2a36d5b76096 | applied revert ea93902f9ba0255e1c7b5cc821fe2a36d5b76096 b9a2dbaab8d747a0b4a354be13688d757e50cdad | ✅ | 394.8s |
| 08-noise #1 | none | none | ✅ | 309.8s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 394.8s
