# Backtest abl-single-rag-r3

Model `qwen/qwen3-14b`, prompt `42356b24`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 25.7s | 18.9s | 13581 | $0.0018 |
| 02-config-regression #1 | VotingHttp5xxRate | ✅ | ✅ | wake → wake ✅ | high | 18.7s | 17.8s | 16325 | $0.0021 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ✅ | ✅ | wake → wake ✅ | high | 64.7s | 58.4s | 18222 | $0.0024 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ✅ | ✅ | wake → wake ✅ | high | 40.7s | 40.4s | 15457 | $0.0021 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 24.7s | 21.4s | 15928 | $0.0021 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → morning ✅ | high | 116.7s | 115.3s | 19212 | $0.0025 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → morning ❌ | high | 45.7s | 35.5s | 13522 | $0.0020 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → morning ❌ | medium | 24.7s | 23.6s | 14336 | $0.0019 |

- **Top-1**: 6/8, **top-3**: 6/8, **triage**: 6/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 33.2s, median investigation 29.55s
- **Median cost**: $0.0021, total $0.0170, median tokens 15692.5

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert a8d0c1b57f34 | applied revert a8d0c1b57f34f03e273d92526e1a4b413cc3b723 91adda448ce9c5d5369e8644ce163ca783240b49 | ✅ | 65.7s |
| 02-config-regression #1 | revert 005da02d05a2 | applied revert 005da02d05a21268a3c5e5e7ff24c5d34b5b30fe 7c32e133000b85bde34579c8d819da42f83f7cd8 | ✅ | 340.7s |
| 03-kafka-broker-down #1 | restart_pod voting-dual-role-1 | applied restart_pod voting-dual-role-1 | ✅ | 426.7s |
| 04-postgres-failover #1 | none | none | ✅ | 280.7s |
| 05-postgres-connections #1 | revert e45d805138e7 | applied revert e45d805138e76eb68a02b5aa7a40d845fa656888 56f114ecc083eae71645ca80d908f51605b75d7b | ✅ | 535.7s |
| 06-replica-lag #1 | revert 56f114ecc083 | applied revert 56f114ecc083eae71645ca80d908f51605b75d7b 939db8796dba5fc5366e74f2d17749fc8a78a85b | ❌ | - |
| 07-redis-oom #1 | revert 5217189596e7 | applied revert 5217189596e77c24d4d77fc16ed3f440ef592642 adcbf100c6ecb68a0f394381e0b157f95712f1d4 | ✅ | 356.7s |
| 08-noise #1 | revert f3f4a1ccc0b1 | applied revert f3f4a1ccc0b1c133119d858a4242bf1fa82de15e 69f90585194987ccdfb41b458073bf6de945c976 | ✅ | 305.7s |

- **Recovered after the agent's fix**: 7/8, median alert → recovery 340.7s
