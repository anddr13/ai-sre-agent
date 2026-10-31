#!/usr/bin/env bash
# Scenario 7, restore: git revert of the limit change and sync; Redis restarts with its old limit.
source "$(dirname "$0")/../lib.sh"
S=07-redis-oom

sha=$(load_state $S sha)
[ -n "$sha" ] || { echo "No break recorded for $S." >&2; exit 1; }

gitops_check
revert=$(gitops_revert "$sha")
log "pushed revert ${revert:0:7} of ${sha:0:7}"
argocd_sync data "$revert" 300
load_stop $S
kubectl -n "$NS" rollout status deploy/redis --timeout=300s > /dev/null
log "Redis rolled out with the previous limit"
# The alert looks at restarts in the last 10 minutes, so it clears 10 minutes after the last kill.
wait_alert ContainerOOMKilled resolved 900
clear_state $S
