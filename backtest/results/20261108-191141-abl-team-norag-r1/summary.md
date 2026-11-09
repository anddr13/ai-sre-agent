# Backtest abl-team-norag-r1

Model `qwen/qwen3-14b + verifier qwen/qwen3-235b-a22b-2507`, prompt `ec894dba`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 01-bad-deploy #1 | VotingPodNotStarting | ✅ | ✅ | wake → wake ✅ | high | 67.8s | 66.8s | 57045 | $0.0080 |
| 02-config-regression #1 | VotingHttp5xxRate | ❌ | ❌ | wake → wake ✅ | low | 64.8s | 62.9s | 61970 | $0.0084 |
| 03-kafka-broker-down #1 | KafkaUnderReplicatedPartitions | ❌ | ❌ | wake → wake ✅ | low | 32.8s | 26.2s | 25625 | $0.0037 |
| 04-postgres-failover #1 | PostgresPrimaryFailover | ❌ | ❌ | wake → wake ✅ | low | 57.8s | 49.5s | 35754 | $0.0054 |
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 102.8s | 102.1s | 73396 | $0.0104 |
| 06-replica-lag #1 | PostgresReplicationLag | ❌ | ❌ | wake|morning → wake ✅ | medium | 187.8s | 180.3s | 90980 | $0.0126 |
| 07-redis-oom #1 | ContainerOOMKilled | ✅ | ✅ | wake → wake ✅ | high | 48.8s | 41.2s | 42901 | $0.0062 |
| 08-noise #1 | VotingApiLatencyHigh | ❌ | ❌ | noise → wake ❌ | high | 106.8s | 101.9s | 49565 | $0.0073 |

- **Top-1**: 3/8, **top-3**: 3/8, **triage**: 7/8
- **Wrong but "high" confidence**: 1/8
- **Median alert → answer**: 66.3s, median investigation 64.85s
- **Median cost**: $0.0076, total $0.0619, median tokens 53305.0

| Scenario | Action | Applied | Recovered | Alert → recovery |
|---|---|---|---|---|
| 01-bad-deploy #1 | revert 6f96b5ba059778ddcec5c618170d8ebd8f41b073 | applied revert 6f96b5ba059778ddcec5c618170d8ebd8f41b073 7db2a56f328835a9249c512130af9f68282c16c3 | ✅ | 127.8s |
| 02-config-regression #1 | none | none | ❌ | - |
| 03-kafka-broker-down #1 | none | none | ❌ | - |
| 04-postgres-failover #1 | none | none | ✅ | 277.8s |
| 05-postgres-connections #1 | revert 36519adc88ef | applied revert 36519adc88ef8155daf5e8fcc7fd23e50d8f9111 33df25d0555c9915c4a095b21765d9611c3ef05f | ✅ | 612.8s |
| 06-replica-lag #1 | none | none | ❌ | - |
| 07-redis-oom #1 | revert e09bad0a991f | applied revert e09bad0a991f514862d644b0788af80a9bc42a7e 6c2b066145f59340ef796dedc42b941bd07e34e9 | ✅ | 350.8s |
| 08-noise #1 | revert e981b9e64264 | applied revert e981b9e64264d1af58469b3186a9173c803bc2c8 247640874e618b37a10e1a36c1c57f26f8d889e5 | ✅ | 307.8s |

- **Recovered after the agent's fix**: 5/8, median alert → recovery 307.8s
