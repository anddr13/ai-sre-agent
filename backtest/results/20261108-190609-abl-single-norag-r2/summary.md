# Backtest abl-single-norag-r2

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 27.7s | 20.3s | 12369 | $0.0016 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ✅ | wake → wake ✅ | high | 40.7s | 38.0s | 14920 | $0.0021 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → morning ❌ | low | 24.7s | 22.1s | 7823 | $0.0011 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | medium | 30.7s | 21.1s | 7937 | $0.0012 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 28.7s | 25.0s | 8890 | $0.0012 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | medium | 35.7s | 30.8s | 9892 | $0.0014 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 29.7s | 20.9s | 13257 | $0.0018 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 23.7s | 19.2s | 8252 | $0.0012 |

- **Top-1**: 3/8, **top-3**: 4/8, **triage**: 6/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 29.2s, median investigation 21.6s
- **Median cost**: $0.0013, total $0.0116, median tokens 9391.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 05e205dd9606 | applied revert 05e205dd96063d739db92bc8e8fd0f9ed8cb49fe 3675ebf9f8d81adb3fc9c56899bb9a9a0b85afc7 | ✅ | 67.7s |
| 02-config-regression #1 | none | none | ❌ | - |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 281.7s |
| 05-postgres-connections #1 | revert 229b0ca2c741 | applied revert 229b0ca2c7415f6acaf73262386ff9a4d52bb582 391ea28ef6e04375e5bf92edd707022f96c23f00 | ✅ | 539.7s |
| 06-replica-lag #1 | revert 391ea28ef6e0 | applied revert 391ea28ef6e04375e5bf92edd707022f96c23f00 1bab00e8744d320dfa4ea788bf1e1e0e2dad845d | ❌ | - |
| 07-redis-oom #1 | revert 5832e5bcb818 | applied revert 5832e5bcb8183dca7312d05f5642684a399fa762 710769c847411fc224a9f7fa10493d6babe1b9e1 | ✅ | 340.7s |
| 08-noise #1 | revert 76d3c4cb00d37c3876a8e418c8a1d5ada54bc60e | applied revert 76d3c4cb00d37c3876a8e418c8a1d5ada54bc60e a89bb6a8bd60a33e0db3fdcce7602cb728998fe3 | ✅ | 314.7s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 314.7s
