#!/usr/bin/env bash
# Backtest stands on EC2: each machine runs the laptop's kind stand (voting-infra-local) and one backtest, so
# ablations and repeats run side by side. Stand N follows its own branch lab-N of voting-gitops, because the
# scenarios commit their breakages there. Run from WSL in the repository root; see cloud/README.md.
#
#   cloud/stands.sh up                   terraform plan + apply (asks), then waits for cloud-init
#   cloud/stands.sh prepare [N...]       branch lab-N, repositories, .env, the stand, tokens, agent-db port-forward
#   cloud/stands.sh run N|all [KEY=value...] ARGS...
#                                        ai-sre-backtest ARGS in tmux on stand N (or every stand), KEY=value over .env
#   cloud/stands.sh status               the last lines of every backtest log
#   cloud/stands.sh collect              backtest/results and audit/ of every stand into this checkout
#   cloud/stands.sh ssh N                a shell on stand N
#   cloud/stands.sh down                 terraform destroy, then the lab-N branches and the deploy key
#   cloud/stands.sh leftovers            anything tagged ai-sre-agent still running in the region
#
# Environment: AWS_PROFILE (gpu-lab-terraform), REGION (eu-north-1), STANDS (3), AGENT_REF (main: the
# ai-sre-agent revision the stands check out; push first), GH (gh, or gh.exe from WSL).
set -euo pipefail
cd "$(dirname "$0")/.."

export AWS_PROFILE=${AWS_PROFILE:-gpu-lab-terraform}
export AWS_REGION=${REGION:-eu-north-1}
STANDS=${STANDS:-3}
AGENT_REF=${AGENT_REF:-main}
OWNER=anddr13
GITOPS_REPO=$OWNER/voting-gitops
GITOPS_DIR=${GITOPS_DIR:-../voting-gitops}
KEY=$HOME/.ssh/ai-sre-stands             # login to the machines
GITOPS_KEY=$HOME/.ssh/ai-sre-stands-gitops # deploy key with write access to voting-gitops, removed by down
KNOWN_HOSTS=$HOME/.ssh/ai-sre-stands.known_hosts
KEY_ID_FILE=cloud/.deploy-key-id
LOGS=cloud/logs
# Only these reach the machines; Slack stays on the laptop (empty values switch it off).
ENV_KEYS=(LLM_BASE_URL LLM_MODEL LLM_API_KEY VERIFIER_MODEL MLFLOW_TRACKING_URI)
GH=${GH:-$(command -v gh || command -v gh.exe || echo gh)}

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

session() {
  aws sts get-caller-identity --query Arn --output text > /dev/null 2>&1 ||
    { echo "AWS session expired: run  aws login --remote --profile gpu-lab" >&2; exit 1; }
}

ips() { terraform -chdir=cloud output -json ips | jq -r '.[]'; }
ip_of() {
  local ip
  ip=$(ips | sed -n "${1}p")
  [ -n "$ip" ] || { echo "no stand $1" >&2; exit 1; }
  echo "$ip"
}
on() { # on N COMMAND...: run on stand N as ubuntu
  local ip
  ip=$(ip_of "$1")
  shift
  ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KNOWN_HOSTS" \
    -o ServerAliveInterval=30 "ubuntu@$ip" "$@"
}
stand_numbers() { if [ $# -gt 0 ]; then echo "$@"; else seq 1 "$(ips | wc -l)"; fi; }

cmd_up() {
  session
  [ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N '' -C ai-sre-stands -f "$KEY"
  local my_ip
  my_ip=$(curl -fsS https://checkip.amazonaws.com)
  terraform -chdir=cloud init -input=false > /dev/null
  terraform -chdir=cloud plan -input=false -out=tfplan -var stands="$STANDS" \
    -var ssh_public_key="$(cat "$KEY.pub")" -var ssh_cidr="$my_ip/32"
  read -r -p "Apply this plan? [y/N] " answer
  [ "$answer" = y ] || { echo "Not applied."; exit 1; }
  terraform -chdir=cloud apply -input=false tfplan
  rm -f cloud/tfplan
  for n in $(stand_numbers); do
    log "stand $n: waiting for SSH and cloud-init"
    until on "$n" true 2> /dev/null; do sleep 5; done
    on "$n" cloud-init status --wait > /dev/null
  done
  log "machines ready: cloud/stands.sh prepare"
}

# The deploy key: one for all stands, write access to voting-gitops only.
deploy_key() {
  [ -f "$GITOPS_KEY" ] || ssh-keygen -q -t ed25519 -N '' -C ai-sre-stands-gitops -f "$GITOPS_KEY"
  [ -s "$KEY_ID_FILE" ] && return
  "$GH" api "repos/$GITOPS_REPO/keys" -f title=ai-sre-stands -f key="$(cat "$GITOPS_KEY.pub")" -F read_only=false \
    --jq .id > "$KEY_ID_FILE"
  log "deploy key $(cat "$KEY_ID_FILE") added to $GITOPS_REPO"
}

prepare_one() {
  local n=$1 branch=lab-$1 env_file
  env_file=$(mktemp)
  for key in "${ENV_KEYS[@]}"; do grep -E "^$key=" .env | tail -1 >> "$env_file" || true; done
  printf 'SLACK_BOT_TOKEN=\nSLACK_CHANNEL=\n' >> "$env_file"
  scp -q -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KNOWN_HOSTS" \
    "$env_file" "ubuntu@$(ip_of "$n"):agent.env"
  scp -q -i "$KEY" -o IdentitiesOnly=yes -o UserKnownHostsFile="$KNOWN_HOSTS" \
    "$GITOPS_KEY" "ubuntu@$(ip_of "$n"):.ssh/gitops"
  rm -f "$env_file"

  # ssh hands the remote shell one string: quote the arguments for it (the name has a space).
  on "$n" "bash -s -- $(printf '%q ' "$branch" "$AGENT_REF" "$OWNER" "$(git -C "$GITOPS_DIR" config user.name)" \
    "$(git -C "$GITOPS_DIR" config user.email)")" << 'EOF'
set -euo pipefail
branch=$1 ref=$2 owner=$3 name=$4 email=$5
chmod 600 ~/.ssh/gitops
ssh-keyscan -q github.com >> ~/.ssh/known_hosts 2> /dev/null
# GITOPS_BRANCH is read by the scenario scripts and by the agent's gitops_log tool.
echo "export GITOPS_BRANCH=$branch MLFLOW_DISABLE_AGENT_HINT=1" > ~/stand.env

[ -d ai-sre-agent ] || git clone -q "https://github.com/$owner/ai-sre-agent.git"
git -C ai-sre-agent fetch -q origin "$ref" && git -C ai-sre-agent checkout -q --detach FETCH_HEAD
[ -d voting-infra-local ] || git clone -q "https://github.com/$owner/voting-infra-local.git"
[ -d voting-gitops ] || git clone -q "git@github.com:$owner/voting-gitops.git"
git -C voting-gitops config core.sshCommand "ssh -i ~/.ssh/gitops -o IdentitiesOnly=yes"
git -C voting-gitops config user.name "$name"
git -C voting-gitops config user.email "$email"
git -C voting-gitops fetch -q origin && git -C voting-gitops checkout -q -B "$branch" "origin/$branch"
mv ~/agent.env ai-sre-agent/.env

cd ai-sre-agent
uv sync -q
GITOPS_REVISION=$branch ../voting-infra-local/scripts/up.sh
export KUBECONFIG=~/.kube/kind-voting-local.yaml
until kubectl get namespace ai-sre-agent > /dev/null 2>&1; do sleep 10; done
scripts/agent-secret.sh
echo "waiting for every Argo CD application to be Healthy"
kubectl -n argocd wait application --all --for=jsonpath='{.status.health.status}'=Healthy --timeout=20m > /dev/null
TOKEN_TTL=96h scripts/agent-kubeconfig.sh
SA=ai-sre-remediator TOKEN_TTL=96h scripts/agent-kubeconfig.sh
tmux kill-session -t db 2> /dev/null || true
tmux new-session -d -s db scripts/agent-db.sh
scripts/check-rbac.sh > /dev/null && echo "RBAC check passed"
echo "stand ready on $branch"
EOF
}

cmd_prepare() {
  [ -f .env ] || { echo "no .env in $(pwd)" >&2; exit 1; }
  deploy_key
  mkdir -p "$LOGS"
  local pids=() n
  # One after another, before the parallel part: they share the local clone.
  git -C "$GITOPS_DIR" fetch -q origin lab
  for n in $(stand_numbers "$@"); do
    # A fresh lab-N from lab: leftovers of an earlier session's scenarios must not carry over.
    git -C "$GITOPS_DIR" push -q --force origin "origin/lab:refs/heads/lab-$n"
    log "stand $n: lab-$n = lab ($(git -C "$GITOPS_DIR" rev-parse --short origin/lab))"
  done
  for n in $(stand_numbers "$@"); do
    prepare_one "$n" > "$LOGS/prepare-$n.log" 2>&1 &
    pids+=($!)
    log "stand $n: preparing (log $LOGS/prepare-$n.log)"
  done
  local failed=0
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  ((failed == 0)) || { echo "a stand failed to prepare, see $LOGS/" >&2; exit 1; }
  log "all stands ready"
}

cmd_run() {
  local target=$1 n
  shift
  # Leading KEY=value arguments are settings for this run only (e.g. VERIFIER_MODEL=), they win over .env.
  local env=() args
  while [[ ${1:-} =~ ^[A-Z_]+= ]]; do
    env+=("$1")
    shift
  done
  printf -v args '%q ' "$@"
  for n in $( [ "$target" = all ] && stand_numbers || echo "$target"); do
    on "$n" tmux has-session -t bt 2> /dev/null && { echo "stand $n: a backtest is still running" >&2; exit 1; }
    # The command goes into a file rather than through two more layers of quoting (ssh, then tmux).
    on "$n" 'cat > ~/run.sh' << EOF
cd ~/ai-sre-agent && . ~/stand.env
${env[*]:+export $(printf '%q ' "${env[@]}")}
echo "=== \$(date -u +%FT%TZ) ${env[*]} ai-sre-backtest $args"
.venv/bin/ai-sre-backtest $args 2>&1 | grep --line-buffered -v 'HTTP Request'
EOF
    on "$n" "tmux new-session -d -s bt 'bash ~/run.sh >> ~/backtest.log 2>&1'"
    log "stand $n: ai-sre-backtest $args"
  done
}

cmd_status() {
  local n
  for n in $(stand_numbers); do
    echo "--- stand $n $(on "$n" 'tmux has-session -t bt 2> /dev/null && echo running || echo idle')"
    on "$n" 'tail -n 4 ~/backtest.log 2> /dev/null' || true
  done
}

cmd_collect() {
  local n ip
  mkdir -p "$LOGS" backtest/results audit
  for n in $(stand_numbers); do
    ip=$(ip_of "$n")
    for dir in backtest/results audit; do
      rsync -a -e "ssh -i $KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$KNOWN_HOSTS" \
        "ubuntu@$ip:ai-sre-agent/$dir/" "$dir/"
    done
    on "$n" 'cat ~/backtest.log 2> /dev/null' > "$LOGS/backtest-$n.log" || true
    log "stand $n collected"
  done
}

cmd_down() {
  session
  local count n
  count=$(ips 2> /dev/null | wc -l) || true
  [ "${count:-0}" -gt 0 ] || count=$STANDS
  terraform -chdir=cloud init -input=false > /dev/null
  # The variables only have to be valid: destroy works from the state.
  terraform -chdir=cloud destroy -var stands="$count" \
    -var ssh_public_key="$(cat "$KEY.pub")" -var ssh_cidr=127.0.0.1/32
  for n in $(seq 1 "$count"); do
    git -C "$GITOPS_DIR" push -q origin --delete "lab-$n" 2> /dev/null && log "deleted branch lab-$n" || true
  done
  if [ -s "$KEY_ID_FILE" ]; then
    "$GH" api -X DELETE "repos/$GITOPS_REPO/keys/$(cat "$KEY_ID_FILE")" && log "deploy key removed"
    rm -f "$KEY_ID_FILE"
  fi
  rm -f "$KNOWN_HOSTS"
}

cmd_leftovers() {
  session
  aws resourcegroupstaggingapi get-resources --tag-filters Key=project,Values=ai-sre-agent \
    --query 'ResourceTagMappingList[].ResourceARN' --output text
}

case "${1:-}" in
  up | prepare | run | status | collect | down | leftovers)
    cmd=$1
    shift
    "cmd_$cmd" "$@"
    ;;
  ssh) on "$2" ;;
  *)
    sed -n '2,17p' "$0" >&2
    exit 2
    ;;
esac
