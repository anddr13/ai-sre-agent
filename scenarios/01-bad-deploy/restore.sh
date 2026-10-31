#!/usr/bin/env bash
# Scenario 1, restore: git revert of the bad release (no reset, no force push), then sync at once.
source "$(dirname "$0")/../lib.sh"
S=01-bad-deploy

sha=$(load_state $S sha)
[ -n "$sha" ] || { echo "No break recorded for $S." >&2; exit 1; }

gitops_check
revert=$(gitops_revert "$sha")
log "pushed revert ${revert:0:7} of ${sha:0:7}"
argocd_sync voting "$revert" 420
wait_voting_healthy 300
wait_alert VotingPodNotStarting resolved 300
clear_state $S
