#!/usr/bin/env bash
# Scenario 6, PostgreSQL replica lag: heavy writes on the primary while the replica stops applying WAL.
#
# The plan said "throttle the replica's I/O"; on kind (local-path volumes inside the Docker VM) there is no
# dependable way to do that, so WAL replay on the replica is paused instead. The replica keeps receiving WAL but
# falls further and further behind, and result-api, which reads through voting-pg-ro, serves stale results.
source "$(dirname "$0")/../lib.sh"
S=06-replica-lag

wait_pg_healthy 120
replica=$(kubectl -n "$NS" get pod -l cnpg.io/cluster=voting-pg,cnpg.io/instanceRole=replica -o jsonpath='{.items[0].metadata.name}')
[ -n "$replica" ] || { echo "no replica found" >&2; exit 1; }
save_state $S replica "$replica"

sed -e "s/{{replica}}/$replica/g" -e "s/{{primary}}/$(pg_primary)/g" \
  "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

load_start $S 300 20m
sleep 20
kubectl -n "$NS" exec "$replica" -c postgres -- psql -qAtc "SELECT pg_wal_replay_pause()" > /dev/null
log "WAL replay paused on $replica"
wait_alert PostgresReplicationLag firing 600
