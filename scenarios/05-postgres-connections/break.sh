#!/usr/bin/env bash
# Scenario 5, PostgreSQL connections: a commit in voting-gitops (lab) lowers max_connections of voting-pg far
# below what the clients need, under load. CloudNativePG restarts the instances with the new value; the
# workers (KEDA scales them up as lag grows) then hit "too many clients" and stop storing votes.
source "$(dirname "$0")/../lib.sh"
S=05-postgres-connections
VALUES=charts/data/values.yaml
LIMIT=${LIMIT:-8}

gitops_check
old=$(sed -nE 's/^    max_connections: "([0-9]+)"$/\1/p' "$GITOPS_DIR/$VALUES")
[ -n "$old" ] || { echo "max_connections not found in $VALUES" >&2; exit 1; }
sed -i -E "s/^(    max_connections: )\"$old\"$/\1\"$LIMIT\"/" "$GITOPS_DIR/$VALUES"
git -C "$GITOPS_DIR" commit -qam "data: max_connections $LIMIT, a smaller footprint for the PostgreSQL instances"
sha=$(gitops_push)
log "pushed ${sha:0:7}: max_connections $old -> $LIMIT"
save_state $S sha "$sha"

sed -e "s/{{revision}}/$sha/g" -e "s/{{old}}/$old/g" -e "s/{{new}}/$LIMIT/g" \
  "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

load_start $S 150 20m
argocd_sync data "$sha" 300
wait_alert PostgresConnectionsHigh firing 600
