#!/usr/bin/env bash
# Scenario 4, PostgreSQL failover: the primary pod of voting-pg is deleted under load.
# CloudNativePG promotes the replica; until then the worker's writes fail.
source "$(dirname "$0")/../lib.sh"
S=04-postgres-failover

wait_pg_healthy 120
primary=$(pg_primary)
load_start $S 100 15m
sleep 20
kubectl -n "$NS" delete pod "$primary" --wait=false > /dev/null
log "deleted the primary $primary"
save_state $S old_primary "$primary"

sed -e "s/{{old_primary}}/$primary/g" "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

wait_alert PostgresPrimaryFailover firing 300
log "primary is now $(pg_primary)"
