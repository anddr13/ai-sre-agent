#!/usr/bin/env bash
# Asserts that the agent's identity is read-only: every "must be no" check has to answer no, every
# "must be yes" check yes. Checked twice: by impersonating the ServiceAccount with the admin kubeconfig, and
# with the agent's own kubeconfig (what the MCP server really uses). Exit code 0 = all checks passed.
set -euo pipefail

CLUSTER=voting-local
SA=system:serviceaccount:ai-sre-agent:ai-sre-agent
admin="$HOME/.kube/kind-$CLUSTER.yaml"
agent="$HOME/.kube/ai-sre-agent.yaml"
if command -v cygpath > /dev/null; then admin=$(cygpath -m "$admin"); agent=$(cygpath -m "$agent"); fi

# "verb resource [namespace]"
MUST_BE_NO=(
  "get secrets voting"
  "list secrets voting"
  "watch secrets voting"
  "get secrets kube-system"
  "create pods/exec voting"
  "get pods/exec voting"
  "create pods/attach voting"
  "create pods/portforward voting"
  "get pods/log voting"
  "delete pods voting"
  "create pods voting"
  "patch deployments.apps voting"
  "update deployments.apps voting"
  "delete deployments.apps voting"
  "create deployments.apps voting"
  "patch statefulsets.apps monitoring"
  "delete clusters.postgresql.cnpg.io voting"
  "patch clusters.postgresql.cnpg.io voting"
  "delete kafkas.kafka.strimzi.io voting"
  "patch applications.argoproj.io argocd"
  "delete applications.argoproj.io argocd"
  "create serviceaccounts/token ai-sre-agent"
  "create clusterrolebindings.rbac.authorization.k8s.io"
  "patch configmaps voting"
  "delete namespaces"
)
MUST_BE_YES=(
  "get pods voting"
  "list events voting"
  "get deployments.apps voting"
  "get statefulsets.apps monitoring"
  "get applications.argoproj.io argocd"
)

failed=0
check() { # check EXPECTED LABEL VERB RESOURCE [NAMESPACE] -- kubectl args...
  local expected=$1 label=$2 verb=$3 resource=$4 ns=${5:-}
  shift 5
  # "pods/exec" would mean "the pod named exec" to kubectl; a subresource needs --subresource.
  local args=("$@" auth can-i "$verb" "${resource%%/*}")
  if [[ "$resource" == */* ]]; then args+=(--subresource "${resource#*/}"); fi
  if [ -n "$ns" ]; then args+=(-n "$ns"); else args+=(--all-namespaces); fi
  local answer
  answer=$(kubectl "${args[@]}" 2> /dev/null || true)
  if [ "$answer" = "$expected" ]; then
    printf '  ok    %-4s %-8s %-45s %s\n' "$answer" "$verb" "$resource" "${ns:-*}"
  else
    printf '  FAIL  %-4s %-8s %-45s %s (%s, expected %s)\n' "${answer:-?}" "$verb" "$resource" "${ns:-*}" "$label" "$expected"
    failed=1
  fi
}

run() { # run LABEL -- kubectl args...
  local label=$1
  shift
  echo "$label"
  local item
  for item in "${MUST_BE_NO[@]}"; do
    read -r verb resource ns <<< "$item"
    check no "$label" "$verb" "$resource" "$ns" "$@"
  done
  for item in "${MUST_BE_YES[@]}"; do
    read -r verb resource ns <<< "$item"
    check yes "$label" "$verb" "$resource" "$ns" "$@"
  done
}

run "impersonating $SA:" --kubeconfig "$admin" --as "$SA"
if [ -f "$agent" ]; then
  run "with the agent's kubeconfig ($agent):" --kubeconfig "$agent"
else
  echo "skipped the agent's kubeconfig: $agent does not exist (scripts/agent-kubeconfig.sh writes it)"
fi

if [ "$failed" -ne 0 ]; then
  echo "RBAC check FAILED" >&2
  exit 1
fi
echo "RBAC check passed: read-only, no secrets, no exec"
