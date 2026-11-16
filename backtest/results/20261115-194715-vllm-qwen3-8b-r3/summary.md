# Backtest vllm-qwen3-8b-r3

Model `Qwen/Qwen3-8B`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 69.7s | 62.1s | 12633 | $0.0000 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ✅ | wake → wake ✅ | high | 127.7s | 122.8s | 16793 | $0.0000 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | high | 62.7s | 59.8s | 12910 | $0.0000 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 65.7s | 57.2s | 13038 | $0.0000 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ❌ | ❌ | wake → wake ✅ | medium | 145.7s | 136.3s | 27276 | $0.0000 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ✅ | wake|morning → morning ✅ | high | 45.7s | 37.9s | 4895 | $0.0000 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 53.7s | 52.4s | 11764 | $0.0000 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | medium | 68.7s | 68.1s | 15482 | $0.0000 |

- **Top-1**: 3/8, **top-3**: 5/8, **triage**: 6/8
- **Wrong but "high" confidence**: 3/8
- **Median alert → answer**: 67.2s, median investigation 60.95s
- **Median cost**: $0.0000, total $0.0000, median tokens 12974.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert ab515385a72865dab35ad584b0a994bf584180b8 | applied revert ab515385a72865dab35ad584b0a994bf584180b8 5a04882a55054a052b33089874b450109dcb8e84 | ✅ | 120.7s |
| 02-config-regression #1 | revert 1665574a458f1a598c1a219e8725b1ccea545665 | applied revert 1665574a458f1a598c1a219e8725b1ccea545665 f72899831e5bb66f3e4622f5aa98bb5a07df780f | ❌ | - |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 276.7s |
| 05-postgres-connections #1 | restart_pod voting-pg-2 | applied restart_pod voting-pg-2 | ❌ | - |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | revert 892f65cd53a1 | applied revert 892f65cd53a1bf4501b46d20d9dafc734e152c57 c09606325f7be8e457dc01a895ba793bcff539e1 | ✅ | 365.7s |
| 08-noise #1 | restart_pod worker-6f4f45cbf6-gh2qk | applied restart_pod worker-6f4f45cbf6-gh2qk | ✅ | 289.7s |

- **Recovered after the agent's fix**: 4/8, median alert → recovery 283.2s
