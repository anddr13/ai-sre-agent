#!/usr/bin/env bash
# Scenario 1, bad deploy: a release commit in voting-gitops (lab) points the voting chart at an image tag
# that does not exist, the way a CI job that bumped the tag but failed to push the image would.
# Expected: the PreSync migrate Job (worker image) cannot pull it, the rollout is stuck, VotingPodNotStarting fires.
source "$(dirname "$0")/../lib.sh"
S=01-bad-deploy
VALUES=charts/voting/values.yaml

gitops_check
old_tag=$(sed -nE 's/^  tag: (.*)$/\1/p' "$GITOPS_DIR/$VALUES")
new_tag=$(head -c 20 /dev/urandom | od -An -tx1 | tr -d ' \n')
sed -i -E "s/^(  tag: ).*/\1$new_tag/" "$GITOPS_DIR/$VALUES"
git -C "$GITOPS_DIR" commit -qam "voting: release ${new_tag:0:7}"
sha=$(gitops_push)
log "pushed ${sha:0:7}: image.tag $old_tag -> $new_tag (does not exist)"
save_state $S sha "$sha"

# The answer is written down before the alert fires, i.e. before the agent can look.
sed -e "s/{{revision}}/$sha/g" -e "s/{{revision7}}/${sha:0:7}/g" -e "s/{{bad_tag}}/$new_tag/g" -e "s/{{bad_tag7}}/${new_tag:0:7}/g" -e "s/{{good_tag}}/$old_tag/g" \
  "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

kubectl -n argocd annotate application root voting argocd.argoproj.io/refresh=hard --overwrite > /dev/null
wait_alert VotingPodNotStarting firing 420
