#!/usr/bin/env bash
# Scenario 8, restore: the alert clears by itself; revert the cosmetic release so the next run starts the same.
source "$(dirname "$0")/../lib.sh"
S=08-noise

sha=$(load_state $S sha)
[ -n "$sha" ] || { echo "No break recorded for $S." >&2; exit 1; }

load_stop $S
gitops_check
revert=$(gitops_revert "$sha")
log "pushed revert ${revert:0:7} of ${sha:0:7}"
argocd_sync voting "$revert" 300
wait_voting_healthy 300
wait_alert VotingApiLatencyHigh resolved 300
clear_state $S
