#!/usr/bin/env bash
# Local access to the agent's Postgres (ai-sre-db) for the backtest and `ai-sre-rag`: writes RAG_DATABASE_URL
# (localhost:$PORT) into .env once, without printing it, then port-forwards until Ctrl-C.
# Uses the admin kubeconfig of the kind stand, never the default one.
set -euo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG="${STAND_KUBECONFIG:-$HOME/.kube/kind-voting-local.yaml}"
[ "$(kubectl config current-context)" = kind-voting-local ] || { echo "not the kind stand" >&2; exit 1; }
PORT=${PORT:-15432}

if ! grep -q '^RAG_DATABASE_URL=' .env 2>/dev/null; then
  uri=$(kubectl -n ai-sre-agent get secret ai-sre-db-app -o jsonpath='{.data.uri}' | base64 -d)
  printf '\nRAG_DATABASE_URL=%s\n' "$(sed -E "s#@[^/]+/#@localhost:$PORT/#" <<<"$uri")" >> .env
  echo "RAG_DATABASE_URL written to .env"
fi
# kubectl port-forward exits when one connection is reset, so it is restarted.
while true; do
  kubectl -n ai-sre-agent port-forward svc/ai-sre-db-rw "$PORT:5432" || true
  sleep 1
done
