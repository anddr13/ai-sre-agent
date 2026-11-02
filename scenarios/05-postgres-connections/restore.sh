#!/usr/bin/env bash
# Scenario 5, restore: stop the load, git revert of the max_connections change, sync, wait for the instances to restart.
source "$(dirname "$0")/../lib.sh"
S=05-postgres-connections

sha=$(load_state $S sha)
[ -n "$sha" ] || { echo "No break recorded for $S." >&2; exit 1; }

# The load first: the instances restart for max_connections, and under 150 votes/s that took over 5 minutes.
load_stop $S
gitops_check
revert=$(gitops_revert "$sha")
log "pushed revert ${revert:0:7} of ${sha:0:7}"
argocd_sync data "$revert" 600
wait_pg_healthy 600
wait_alert PostgresConnectionsHigh resolved 420
clear_state $S
