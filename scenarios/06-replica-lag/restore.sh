#!/usr/bin/env bash
# Scenario 6, restore: resume WAL replay on the replica, stop the load, wait for it to catch up.
source "$(dirname "$0")/../lib.sh"
S=06-replica-lag

replica=$(load_state $S replica)
[ -n "$replica" ] || { echo "No break recorded for $S." >&2; exit 1; }

# A restart of the replica (the agent's fix) already ends the pause; it has to be up again for psql.
kubectl -n "$NS" wait pod "$replica" --for=condition=Ready --timeout=300s > /dev/null
kubectl -n "$NS" exec "$replica" -c postgres -- psql -qAtc "SELECT pg_wal_replay_resume()" > /dev/null
log "WAL replay resumed on $replica"
load_stop $S
wait_alert PostgresReplicationLag resolved 600
clear_state $S
