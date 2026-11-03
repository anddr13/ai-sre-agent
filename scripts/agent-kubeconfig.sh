#!/usr/bin/env bash
# Writes ~/.kube/ai-sre-agent.yaml: a kubeconfig for the kind stand that authenticates as the agent's own
# read-only ServiceAccount (deploy/rbac.yaml) with a short-lived token. The MCP server uses this file, never the
# admin kubeconfig. Run it again when the token expires (TOKEN_TTL, default 24h).
# SA=ai-sre-remediator writes ~/.kube/ai-sre-remediator.yaml for the backtest's fixes (deploy/remediator.yaml).
set -euo pipefail

CLUSTER=voting-local
TOKEN_TTL=${TOKEN_TTL:-24h}
admin="$HOME/.kube/kind-$CLUSTER.yaml"
SA=${SA:-ai-sre-agent}
out="$HOME/.kube/$SA.yaml"
if command -v cygpath > /dev/null; then admin=$(cygpath -m "$admin"); out=$(cygpath -m "$out"); fi

if [ "$(kubectl --kubeconfig "$admin" config current-context)" != "kind-$CLUSTER" ]; then
  echo "Refusing to run: $admin does not point at kind-$CLUSTER." >&2
  exit 1
fi

server=$(kubectl --kubeconfig "$admin" config view --minify -o jsonpath='{.clusters[0].cluster.server}')
ca=$(kubectl --kubeconfig "$admin" config view --minify --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
token=$(kubectl --kubeconfig "$admin" -n ai-sre-agent create token "$SA" --duration="$TOKEN_TTL")

umask 077
cat > "$out" << EOF
apiVersion: v1
kind: Config
clusters:
  - name: kind-$CLUSTER
    cluster:
      server: $server
      certificate-authority-data: $ca
users:
  - name: $SA
    user:
      token: $token
contexts:
  - name: $SA@kind-$CLUSTER
    context:
      cluster: kind-$CLUSTER
      user: $SA
current-context: $SA@kind-$CLUSTER
EOF
echo "wrote $out (ServiceAccount ai-sre-agent/$SA, token valid for $TOKEN_TTL)"
