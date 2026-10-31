# Shared helpers for scenarios/NN-name/{break,restore}.sh. Sourced, not run.
#
# The scripts break the kind stand from voting-infra-local and put it back. They act with the kind admin
# kubeconfig and push to the lab branch of voting-gitops: that is the "backtest" identity with write access.
# The agent never runs them and never gets these rights.
#
# Environment:
#   GITOPS_DIR  voting-gitops checkout on the lab branch (default: ../voting-gitops next to this repo)
#   K6_IMAGE    k6 image for the background load (default grafana/k6:2.3.0)

set -euo pipefail

SCENARIOS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
STATE_DIR="$SCENARIOS_DIR/.state"
GITOPS_DIR=${GITOPS_DIR:-$SCENARIOS_DIR/../../voting-gitops}
GITOPS_BRANCH=lab
CLUSTER=voting-local
NODE=$CLUSTER-control-plane
NS=voting
K6_IMAGE=${K6_IMAGE:-grafana/k6:2.3.0}

kubeconfig="$HOME/.kube/kind-$CLUSTER.yaml"
if command -v cygpath > /dev/null; then # Git Bash on Windows: native tools need C:/... paths
  kubeconfig=$(cygpath -m "$kubeconfig")
  GITOPS_DIR=$(cygpath -m "$GITOPS_DIR")
  STATE_DIR=$(cygpath -m "$STATE_DIR")
fi
export KUBECONFIG=${KUBECONFIG:-$kubeconfig}
# Git Bash would turn /opt/... arguments of kubectl exec into Windows paths.
export MSYS_NO_PATHCONV=1

if [ "$(kubectl config current-context)" != "kind-$CLUSTER" ]; then
  echo "Refusing to run: kubectl context is '$(kubectl config current-context)', expected 'kind-$CLUSTER'." >&2
  exit 1
fi
mkdir -p "$STATE_DIR"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

# --- state shared between break.sh and restore.sh ---------------------------------------------------

# save_state SCENARIO KEY VALUE / load_state SCENARIO KEY
save_state() { echo "$3" > "$STATE_DIR/$1.$2"; }
load_state() { cat "$STATE_DIR/$1.$2" 2> /dev/null || true; }
clear_state() { rm -f "$STATE_DIR/$1".*; }

# --- Prometheus, through Grafana's datasource proxy (the stand's only HTTP entry point) -----------

prom_query() {
  curl -fsS -H 'Host: grafana.localhost' -G "http://localhost:8090/api/datasources/proxy/uid/prometheus/api/v1/query" \
    --data-urlencode "query=$1"
}

# alert_firing NAME: exit 0 if the voting alert NAME is firing now.
alert_firing() {
  prom_query "ALERTS{alertname=\"$1\",stand=\"voting\",alertstate=\"firing\"}" | grep -q '"alertname"'
}

# wait_alert NAME firing|resolved TIMEOUT_S
wait_alert() {
  local name=$1 want=$2 timeout=${3:-600} start=$SECONDS
  log "waiting for $name to be $want (up to ${timeout}s)"
  while ((SECONDS - start < timeout)); do
    if [ "$want" = firing ] && alert_firing "$name"; then log "$name is firing after $((SECONDS - start))s"; return 0; fi
    if [ "$want" = resolved ] && ! alert_firing "$name"; then log "$name is not firing after $((SECONDS - start))s"; return 0; fi
    sleep 10
  done
  log "TIMEOUT: $name did not become $want" >&2
  return 1
}

# --- load -----------------------------------------------------------------------------------------

# load_start SCENARIO RATE DURATION: k6 in the background on the kind network, straight to Traefik.
load_start() {
  local name="k6-$1"
  docker rm -f "$name" > /dev/null 2>&1 || true
  # Detached, so the script cannot come in on stdin: copy it into the container before it starts.
  docker create --rm --name "$name" --network kind -e BASE_URL="http://$NODE:30080" \
    -e RATE="$2" -e DURATION="$3" "$K6_IMAGE" run --quiet /tmp/load.js > /dev/null
  (cd "$SCENARIOS_DIR" && docker cp load.js "$name:/tmp/load.js")
  docker start "$name" > /dev/null
  log "k6: $2 votes/s for $3 (container $name)"
}
load_stop() { docker rm -f "k6-$1" > /dev/null 2>&1 && log "k6 stopped" || true; }

# --- GitOps: commit to lab, then make Argo CD apply it now --------------------------------------------

gitops_check() {
  local branch
  branch=$(git -C "$GITOPS_DIR" rev-parse --abbrev-ref HEAD)
  if [ "$branch" != "$GITOPS_BRANCH" ]; then
    echo "Refusing to run: $GITOPS_DIR is on '$branch', expected '$GITOPS_BRANCH'." >&2
    exit 1
  fi
  if [ -n "$(git -C "$GITOPS_DIR" status --porcelain)" ]; then
    echo "Refusing to run: $GITOPS_DIR has uncommitted changes." >&2
    exit 1
  fi
  git -C "$GITOPS_DIR" pull -q --ff-only
}

# gitops_push: pushes HEAD of lab and prints its sha.
gitops_push() {
  git -C "$GITOPS_DIR" push -q origin "$GITOPS_BRANCH"
  git -C "$GITOPS_DIR" rev-parse HEAD
}

# gitops_revert SHA: a revert commit, never a reset or force push, so the history shows deploy -> rollback.
gitops_revert() {
  git -C "$GITOPS_DIR" revert --no-edit "$1" > /dev/null
  gitops_push
}

# argocd_sync APP SHA [TIMEOUT_S]: applies revision SHA now instead of after the 3-minute poll.
# A hard refresh makes Argo CD re-read the repo; the app's automated sync then starts at once.
# An operation stuck on an older revision (e.g. a PreSync hook that can never pull its image) is terminated.
argocd_sync() {
  local app=$1 sha=$2 timeout=${3:-300} start=$SECONDS
  kubectl -n argocd annotate application root "$app" argocd.argoproj.io/refresh=hard --overwrite > /dev/null
  while ((SECONDS - start < timeout)); do
    local phase op_rev rev status health
    phase=$(kubectl -n argocd get application "$app" -o jsonpath='{.status.operationState.phase}')
    op_rev=$(kubectl -n argocd get application "$app" -o jsonpath='{.status.operationState.syncResult.revision}{.status.operationState.operation.sync.revision}')
    # jsonpath prints no trailing newline, so read hits EOF and returns 1 even though it read the line.
    read -r rev status health < <(kubectl -n argocd get application "$app" \
      -o jsonpath='{.status.sync.revision} {.status.sync.status} {.status.health.status}') || true
    if [ "$phase" = Running ] && [[ "$op_rev" != *"$sha"* ]]; then
      log "terminating the running operation of $app (it is on another revision)"
      kubectl -n argocd patch application "$app" --type merge -p '{"status":{"operationState":{"phase":"Terminating"}}}' > /dev/null
    fi
    # Synced = the live objects match revision SHA (a terminated sync of a bad revision that never got past
    # its PreSync hook leaves them matching the good one, so no new sync is needed in that case).
    if [ "$rev" = "$sha" ] && [ "$status" = Synced ] && [ "$health" = Healthy ] &&
      [ "$phase" != Running ] && [ "$phase" != Terminating ]; then
      log "$app is Synced and Healthy at ${sha:0:7} (last operation: ${phase:-none})"
      return 0
    fi
    sleep 5
  done
  log "TIMEOUT: $app did not reach ${sha:0:7}" >&2
  return 1
}

# --- the kind node: processes of a pod's container, as seen by the node ---------------------------

# container_pid POD CONTAINER: host PID of the container's main process.
container_pid() {
  docker exec "$NODE" sh -c "id=\$(crictl ps -q --name '^$2\$' --label io.kubernetes.pod.name=$1 | head -1);
    crictl inspect -o go-template --template '{{.info.pid}}' \"\$id\""
}

# --- PostgreSQL ------------------------------------------------------------------------------------

# Prints the primary pod, or "none" in the middle of a failover (no pod carries the primary label yet).
pg_primary() {
  local p
  p=$(kubectl -n "$NS" get pod -l cnpg.io/cluster=voting-pg,cnpg.io/instanceRole=primary -o jsonpath='{.items[*].metadata.name}')
  echo "${p:-none}"
}

# wait_pg_healthy TIMEOUT_S: all instances ready and a primary elected.
wait_pg_healthy() {
  kubectl -n "$NS" wait cluster/voting-pg --for=condition=Ready --timeout="${1:-300}s" > /dev/null
  log "PostgreSQL cluster ready, primary $(pg_primary)"
}

# wait_voting_healthy TIMEOUT_S: every Deployment in the namespace has finished rolling out.
wait_voting_healthy() {
  local d
  for d in $(kubectl -n "$NS" get deploy -o name); do
    kubectl -n "$NS" rollout status "$d" --timeout="${1:-300}s" > /dev/null
  done
  log "all Deployments in $NS rolled out"
}
