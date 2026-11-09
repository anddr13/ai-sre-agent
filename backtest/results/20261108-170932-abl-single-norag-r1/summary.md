# Backtest abl-single-norag-r1

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 23.9s | 18.0s | 8792 | $0.0012 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | medium | 38.9s | 30.6s | 10647 | $0.0016 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | high | 65.9s | 62.1s | 9934 | $0.0014 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | high | 18.9s | 17.8s | 7015 | $0.0010 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 30.9s | 28.7s | 10230 | $0.0014 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | high | 48.9s | 41.9s | 11393 | $0.0017 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 49.9s | 48.1s | 12535 | $0.0017 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 43.9s | 41.8s | 9623 | $0.0013 |

- **Top-1**: 4/8, **top-3**: 4/8, **triage**: 7/8
- **Wrong but "high" confidence**: 4/8
- **Median alert → answer**: 41.4s, median investigation 36.2s
- **Median cost**: $0.0014, total $0.0112, median tokens 10082.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 6ac6fece91d5 | applied revert 6ac6fece91d5166c85212de4ecfde50f94e90f3b 512f3285a954cb11ac26ae03ee350a7fa7bc551f | ✅ | 63.9s |
| 02-config-regression #1 | revert 47432bc62fe3 | applied revert 47432bc62fe3977169ec31d326885dfd85d20ab2 2279168e1d36e3f94915c22a6d796e37e585fe62 | ✅ | 366.9s |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 289.9s |
| 05-postgres-connections #1 | revert 3493fac46be2 | applied revert 3493fac46be24ad101ab269c3eb718dff2ea0378 6a68c2b84935609fcb40ad1582e39def59c8d227 | ✅ | 541.9s |
| 06-replica-lag #1 | revert 3493fac46be2 | rejected: 3493fac46be2 is already reverted | ❌ | - |
| 07-redis-oom #1 | revert b07670e0c73a | applied revert b07670e0c73a95479be8f3cad6d746c6f462dc46 9449bc0a3d9f707edbbfc7f7bb71c1d8939763b4 | ✅ | 366.9s |
| 08-noise #1 | revert 643a6ac1b65ed0466b202b3e720a9515a17beb5a | applied revert 643a6ac1b65ed0466b202b3e720a9515a17beb5a edf874002c7fe4edabfceccbdeff3cbed6c01efb | ✅ | 303.9s |

- **Recovered after the agent's fix**: 6/8, median alert → recovery 335.4s
