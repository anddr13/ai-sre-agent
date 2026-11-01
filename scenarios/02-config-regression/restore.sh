#!/usr/bin/env bash
# Scenario 2, restore: git revert of the release, sync, wait for the 5xx to stop.
source "$(dirname "$0")/../lib.sh"
S=02-config-regression

sha=$(load_state $S sha)
[ -n "$sha" ] || { echo "No break recorded for $S." >&2; exit 1; }

gitops_check
revert=$(gitops_revert "$sha")
log "pushed revert ${revert:0:7} of ${sha:0:7}"
argocd_sync voting "$revert" 300
wait_voting_healthy 300
load_stop $S
wait_alert VotingHttp5xxRate resolved 420
clear_state $S
