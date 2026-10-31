#!/usr/bin/env bash
# Creates (or updates) the Secret ai-sre-agent-env on the kind stand from the local .env: the LLM key and the
# Slack token reach the cluster without ever being committed. Only the variables the agent needs are copied.
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=voting-local
KEYS=(LLM_BASE_URL LLM_MODEL LLM_API_KEY SLACK_BOT_TOKEN SLACK_CHANNEL)
admin="$HOME/.kube/kind-$CLUSTER.yaml"
if command -v cygpath > /dev/null; then admin=$(cygpath -m "$admin"); fi

if [ "$(kubectl --kubeconfig "$admin" config current-context)" != "kind-$CLUSTER" ]; then
  echo "Refusing to run: $admin does not point at kind-$CLUSTER." >&2
  exit 1
fi
[ -f .env ] || { echo "no .env in $(pwd)" >&2; exit 1; }

# Values go through a private temporary file, not the command line (where any process listing would show them).
umask 077
envfile=$(mktemp)
trap 'rm -f "$envfile"' EXIT
for key in "${KEYS[@]}"; do
  grep -E "^$key=" .env | tail -1 >> "$envfile" || { echo "$key is missing in .env" >&2; exit 1; }
done
if command -v cygpath > /dev/null; then envpath=$(cygpath -m "$envfile"); else envpath=$envfile; fi

kubectl --kubeconfig "$admin" -n ai-sre-agent create secret generic ai-sre-agent-env --from-env-file="$envpath" \
  --dry-run=client -o yaml | kubectl --kubeconfig "$admin" apply -f - > /dev/null
echo "Secret ai-sre-agent/ai-sre-agent-env updated with: ${KEYS[*]}"
