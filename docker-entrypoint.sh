#!/bin/sh
# gitops_log reads a clone of the GitOps repository; make one on first start (the tool fetches on every call).
set -eu
if [ -n "${GITOPS_REPO:-}" ] && [ -n "${GITOPS_URL:-}" ] && [ ! -d "$GITOPS_REPO/.git" ]; then
  git clone --quiet --no-checkout "$GITOPS_URL" "$GITOPS_REPO"
fi
exec "$@"
