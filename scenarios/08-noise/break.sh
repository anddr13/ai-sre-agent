#!/usr/bin/env bash
# Scenario 8, noise: a harmless release (only the stand name shown in the UI changes, every voting pod is replaced)
# followed by a one-minute traffic burst. The deliberately sensitive VotingApiLatencyHigh fires and resolves by
# itself; nothing is broken. The right answer is "noise, do not wake anyone", despite the deploy right before it.
source "$(dirname "$0")/../lib.sh"
S=08-noise
VALUES=envs/local.yaml

gitops_check
grep -qE '^      cloudName: kind$' "$GITOPS_DIR/$VALUES" || { echo "cloudName: kind not found in $VALUES" >&2; exit 1; }
sed -i -E 's/^(      cloudName: )kind$/\1kind-lab/' "$GITOPS_DIR/$VALUES"
git -C "$GITOPS_DIR" commit -qam "voting: show the stand as kind-lab in the UI"
sha=$(gitops_push)
log "pushed ${sha:0:7}: cloudName kind -> kind-lab"
save_state $S sha "$sha"

sed -e "s/{{revision}}/$sha/g" -e "s/{{revision7}}/${sha:0:7}/g" \
  "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

argocd_sync voting "$sha" 300
wait_voting_healthy 300
load_start $S 2500 60s
wait_alert VotingApiLatencyHigh firing 240
