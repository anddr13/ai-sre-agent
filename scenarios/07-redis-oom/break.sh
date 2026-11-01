#!/usr/bin/env bash
# Scenario 7, Redis OOM: a commit in voting-gitops (lab) cuts the memory limit of Redis below what it uses
# under load (its maxmemory, 96mb, now exceeds the limit too). The kernel kills it: OOMKilled, restarts,
# and while it is down vote-api cannot check the rate limit and answers 5xx.
source "$(dirname "$0")/../lib.sh"
S=07-redis-oom
VALUES=charts/data/values.yaml
LIMIT=${LIMIT:-10Mi}

gitops_check
# The Redis block is the only one with a 64Mi request and a 128Mi limit in the chart's values. Both go
# down together: a request above the limit would be rejected by the API server, and the sync would fail
# instead of Redis being killed.
old=$(sed -nE 's/^    limits: \{ memory: (128Mi) \}$/\1/p' "$GITOPS_DIR/$VALUES")
[ -n "$old" ] || { echo "the Redis memory limit (128Mi) was not found in $VALUES" >&2; exit 1; }
sed -i -E -e "s/^(    limits: \{ memory: )128Mi( \})$/\1$LIMIT\2/" \
  -e "s/^(    requests: \{ cpu: 25m, memory: )64Mi( \})$/\1$LIMIT\2/" "$GITOPS_DIR/$VALUES"
git -C "$GITOPS_DIR" commit -qam "data: Redis memory $LIMIT, it only holds counters and rate-limit keys"
sha=$(gitops_push)
log "pushed ${sha:0:7}: Redis memory limit $old -> $LIMIT"
save_state $S sha "$sha"

sed -e "s/{{revision}}/$sha/g" -e "s/{{revision7}}/${sha:0:7}/g" -e "s/{{old}}/$old/g" -e "s/{{new}}/$LIMIT/g" \
  "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

load_start $S 300 20m
argocd_sync data "$sha" 300
wait_alert ContainerOOMKilled firing 600
