# Backtest team-rag-05

Model `qwen/qwen3-14b`, prompt `b4aa45d8`.

| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| 05-postgres-connections #1 | PostgresConnectionsHigh | ✅ | ✅ | wake → wake ✅ | high | 252.4s | 211.0s | 50090 | $0.0075 |

- **Top-1**: 1/1, **top-3**: 1/1, **triage**: 1/1
- **Wrong but "high" confidence**: 0/1
- **Median alert → answer**: 252.4s, median investigation 211.0s
- **Median cost**: $0.0075, total $0.0075, median tokens 50090
