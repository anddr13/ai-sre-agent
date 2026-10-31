# PostgresReplicationLag

**Symptom.** A replica of `voting-pg` has been more than 30 seconds behind the primary for a minute.
result-api reads through `voting-pg-ro` (replicas only), so results are stale: votes are stored, but the
numbers lag behind.

## What to check

1. Which replica and how far behind: `cnpg_pg_replication_lag{namespace="voting"}`; on the primary,
   `cnpg_pg_stat_replication_*_lag_seconds` per replica (write, flush, replay).
2. Is replay or the stream the problem: received vs replayed WAL on the replica. Received but not replayed
   means the replica is slow to apply (I/O, CPU, a long query blocking replay); not received means network
   or the WAL sender.
3. Write load on the primary right now: worker throughput (`worker_votes_total`), Kafka consumer lag catching up.
4. Resources of the replica pod: CPU throttling, memory, disk I/O; did its limits change?
5. Replay paused on purpose? `pg_is_wal_replay_paused()` on the replica.

## Typical causes

- A burst of writes (e.g. the worker catching up on Kafka lag) faster than the replica can replay.
- The replica is starved of I/O or CPU (limits too low, noisy neighbour).
- Replay paused or blocked by a long-running query on the replica.

## Mitigation

- Temporary burst: lag shrinks once the backlog is written; nothing to do but watch.
- Starved replica: give it back its resources (revert the limits change).
- Paused replay: resume it (`pg_wal_replay_resume()`).
- If stale reads hurt more than load on the primary, point result-api at `voting-pg-rw` until the replica catches up.
