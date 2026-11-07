#!/usr/bin/env bash
# Applies the fix the agent proposed, in the backtest only, and only one of the allowed actions
# (investigator.parse_action):
#   apply-fix.sh revert SHA        git revert of a recent commit of voting-gitops (lab), then an Argo CD sync
#   apply-fix.sh restart_pod POD   delete one pod in namespace voting, as the ServiceAccount ai-sre-remediator
#   apply-fix.sh undo SHA          revert the agent's revert commit SHA again (it reverted the wrong commit)
# The last line of the output is "applied ..." or "rejected <why>"; a rejected fix is not an error.
source "$(dirname "$0")/lib.sh"

# deploy/remediator.yaml; written by `SA=ai-sre-remediator scripts/agent-kubeconfig.sh`.
remediator="$HOME/.kube/ai-sre-remediator.yaml"
if command -v cygpath > /dev/null; then remediator=$(cygpath -m "$remediator"); fi

# The Application whose files a commit changes.
app_of() {
  local files
  files=$(git -C "$GITOPS_DIR" show --name-only --format= "$1")
  if grep -q '^charts/data/' <<< "$files"; then
    echo data
  elif grep -q '^charts/alerts/' <<< "$files"; then
    echo alerts
  else
    echo voting
  fi
}

# revert_and_sync SHA: prints the revert commit, or "" when SHA does not revert cleanly.
revert_and_sync() {
  if ! git -C "$GITOPS_DIR" revert --no-edit "$1" > /dev/null 2>&1; then
    git -C "$GITOPS_DIR" revert --abort 2> /dev/null || true
    return
  fi
  local revert
  revert=$(gitops_push)
  log "reverted ${1:0:7} as ${revert:0:7}" >&2
  argocd_sync "$(app_of "$1")" "$revert" 600 >&2
  echo "$revert"
}

case "${1:-}" in
  revert)
    gitops_check
    sha=$(git -C "$GITOPS_DIR" rev-parse --verify --quiet "${2}^{commit}") ||
      { echo "rejected: $2 is not a commit of voting-gitops"; exit 0; }
    # A recent commit only: the fix of an incident, not a rewrite of history.
    # (Not `rev-list | grep -q`: grep stops at the match, git gets SIGPIPE, and pipefail calls it a failure.)
    recent=$(git -C "$GITOPS_DIR" rev-list -n 30 HEAD)
    grep -qx "$sha" <<< "$recent" ||
      { echo "rejected: $2 is not among the last 30 commits of $GITOPS_BRANCH"; exit 0; }
    [ -z "$(git -C "$GITOPS_DIR" log --format=%H --grep="This reverts commit $sha" HEAD)" ] ||
      { echo "rejected: $2 is already reverted"; exit 0; }
    revert=$(revert_and_sync "$sha")
    [ -n "$revert" ] || { echo "rejected: $2 does not revert cleanly"; exit 0; }
    echo "applied revert $sha $revert"
    ;;
  restart_pod)
    kubectl --kubeconfig "$remediator" -n "$NS" delete pod "$2" --wait=false > /dev/null ||
      { echo "rejected: cannot delete pod $2 in $NS"; exit 0; }
    log "deleted pod $2"
    echo "applied restart_pod $2"
    ;;
  undo)
    gitops_check
    revert=$(revert_and_sync "$2")
    [ -n "$revert" ] || { echo "undo of $2 failed: it does not revert cleanly" >&2; exit 1; }
    echo "applied undo $2 $revert"
    ;;
  *)
    echo "usage: $0 revert SHA | restart_pod POD | undo SHA" >&2
    exit 2
    ;;
esac
