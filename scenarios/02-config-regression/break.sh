#!/usr/bin/env bash
# Scenario 2, regression after a deploy: a release commit in voting-gitops (lab) "makes the unit explicit" in
# vote-api's rate-limit window, RATE_LIMIT_SECONDS "3" -> "3s". The pods start and pass their readiness probe,
# so the rollout completes; but Number("3s") is NaN, Redis rejects SET ... EX NaN, and every vote gets a 500.
source "$(dirname "$0")/../lib.sh"
S=02-config-regression
VALUES=charts/voting/values.yaml

gitops_check
grep -qE '^      RATE_LIMIT_SECONDS: "3"$' "$GITOPS_DIR/$VALUES" || { echo "RATE_LIMIT_SECONDS \"3\" not found in $VALUES" >&2; exit 1; }
sed -i -E 's/^(      RATE_LIMIT_SECONDS: )"3"$/\1"3s"/' "$GITOPS_DIR/$VALUES"
git -C "$GITOPS_DIR" commit -qam "vote-api: rate limit window with an explicit unit (3s)"
sha=$(gitops_push)
log "pushed ${sha:0:7}: RATE_LIMIT_SECONDS \"3\" -> \"3s\""
save_state $S sha "$sha"

sed -e "s/{{revision}}/$sha/g" -e "s/{{revision7}}/${sha:0:7}/g" \
  "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

load_start $S 50 20m
argocd_sync voting "$sha" 300
wait_alert VotingHttp5xxRate firing 600
