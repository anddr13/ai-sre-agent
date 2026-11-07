#!/usr/bin/env bash
# Backtest stands on GCE: each machine runs the laptop's kind stand (voting-infra-local) and one backtest, so
# ablations and repeats run side by side. The scenarios commit their breakages, so the stands follow a copy of
# voting-gitops, voting-gitops-backtest (Actions off), never voting-gitops itself; stand N has its branch lab-N
# there. Everything long runs in tmux on the machines: the laptop may switch off after `run`. Run from Git Bash in
# the repository root; see cloud/README.md.
#
#   cloud/stands.sh plan                 terraform plan into cloud/tfplan (read it)
#   cloud/stands.sh up                   apply cloud/tfplan, then wait for SSH and cloud-init
#   cloud/stands.sh prepare [N...]       the copy (created once), lab-N = lab of voting-gitops, deploy key, .env;
#                                        the stand itself comes up in tmux (~20 min)
#   cloud/stands.sh run N|all [KEY=value...] ARGS...
#                                        ai-sre-backtest ARGS in tmux on stand N (or every stand), once it is
#                                        prepared; KEY=value wins over .env
#   cloud/stands.sh status               prepare and backtest state of every stand
#   cloud/stands.sh collect              backtest/results and audit/ of every stand into this checkout
#   cloud/stands.sh ssh N                a shell on stand N
#   cloud/stands.sh down                 terraform destroy, then the lab-N branches and the deploy key of the copy
#   cloud/stands.sh leftovers            anything labelled ai-sre-agent still in the project
#
# Environment: PROJECT (voting-gke-cdzjn), STANDS (3), AGENT_REF (main: the ai-sre-agent revision the stands
# check out; push first), GH (gh).
set -euo pipefail

# From WSL: run again in Git Bash. gcloud, gh, terraform (with its Windows provider) and the stands' SSH key all
# live on the Windows side. WSLENV hands the settings above over to it.
if grep -qi microsoft /proc/version 2> /dev/null; then
  export WSLENV=PROJECT:STANDS:AGENT_REF:GH:${WSLENV:-}
  exec "/mnt/c/Program Files/Git/bin/bash.exe" "$(wslpath -w "$(realpath "$0")")" "$@"
fi
cd "$(dirname "$0")/.."

PROJECT=${PROJECT:-voting-gke-cdzjn}
STANDS=${STANDS:-3}
AGENT_REF=${AGENT_REF:-main}
OWNER=anddr13
GITOPS_REPO=$OWNER/voting-gitops-backtest   # the copy the stands follow and push to
GITOPS_DIR=${GITOPS_DIR:-../voting-gitops}  # the laptop's clone of the original: the source of lab, read only
KEY=$HOME/.ssh/ai-sre-stands                # login to the machines
GITOPS_KEY=$HOME/.ssh/ai-sre-stands-gitops  # deploy key of the copy (write), removed by down
KNOWN_HOSTS=$HOME/.ssh/ai-sre-stands.known_hosts
KEY_ID_FILE=cloud/.deploy-key-id
LOGS=cloud/logs
# Only these reach the machines; Slack stays on the laptop (empty values switch it off).
ENV_KEYS=(LLM_BASE_URL LLM_MODEL LLM_API_KEY VERIFIER_MODEL MLFLOW_TRACKING_URI)
GH=${GH:-gh}

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

session() {
  gcloud auth application-default print-access-token > /dev/null 2>&1 ||
    { echo "No Google credentials: run  gcloud auth application-default login" >&2; exit 1; }
}

tf() { terraform -chdir=cloud "$@"; }
tf_vars() { # the variables only have to be valid for destroy, which works from the state
  echo -var project_id="$PROJECT" -var stands="$1" -var ssh_cidr="$2"
}
ips() { tf output -raw ips; echo; } # -raw prints no final newline, and wc -l counts newlines
ip_of() {
  local ip
  ip=$(ips | sed -n "${1}p")
  [ -n "$ip" ] || { echo "no stand $1" >&2; exit 1; }
  echo "$ip"
}
SSH_OPTS=(-i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="$KNOWN_HOSTS"
  -o ServerAliveInterval=30)
on() { # on N COMMAND...: run on stand N as ubuntu
  local ip
  ip=$(ip_of "$1")
  shift
  ssh "${SSH_OPTS[@]}" "ubuntu@$ip" "$@"
}
copy_to() { scp -q "${SSH_OPTS[@]}" "$2" "ubuntu@$(ip_of "$1"):$3"; } # copy_to N LOCAL REMOTE
stand_numbers() { if [ $# -gt 0 ]; then echo "$@"; else seq 1 "$(ips | wc -l)"; fi; }

cmd_plan() {
  session
  [ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N '' -C ai-sre-stands -f "$KEY"
  local my_ip
  my_ip=$(curl -fsS https://checkip.amazonaws.com)
  tf init -input=false > /dev/null
  # shellcheck disable=SC2046 # word splitting of tf_vars is the point
  tf plan -input=false -out=tfplan $(tf_vars "$STANDS" "$my_ip/32") -var ssh_public_key="$(cat "$KEY.pub")"
  echo "Read the plan above, then: cloud/stands.sh up"
}

cmd_up() {
  session
  [ -f cloud/tfplan ] || { echo "no cloud/tfplan: run cloud/stands.sh plan first" >&2; exit 1; }
  tf apply -input=false tfplan
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
  [ "$GITOPS_REPO" != "$OWNER/voting-gitops" ] || { echo "Refusing: the stands never push to voting-gitops." >&2; exit 1; }
  [ -f "$GITOPS_KEY" ] || ssh-keygen -q -t ed25519 -N '' -C ai-sre-stands-gitops -f "$GITOPS_KEY"
  [ -s "$KEY_ID_FILE" ] && return
  "$GH" api "repos/$GITOPS_REPO/keys" -f title=ai-sre-stands -f key="$(cat "$GITOPS_KEY.pub")" -F read_only=false \
    --jq .id > "$KEY_ID_FILE"
  log "deploy key $(cat "$KEY_ID_FILE") added to $GITOPS_REPO"
}

# Runs on the machine, in tmux: brings the stand up from the repositories. Settings come from ~/stand.env.
PREPARE=$(
  cat << 'EOF'
set -euo pipefail
trap 'echo "FAILED at line $LINENO: $BASH_COMMAND"' ERR
. ~/stand.env
chmod 600 ~/.ssh/gitops
# No -q: Ubuntu 24.04's ssh-keyscan (OpenSSH 9.6) does not have it.
ssh-keyscan github.com >> ~/.ssh/known_hosts 2> /dev/null

[ -d ai-sre-agent ] || git clone -q "https://github.com/$OWNER/ai-sre-agent.git"
git -C ai-sre-agent fetch -q origin "$AGENT_REF" && git -C ai-sre-agent checkout -q --detach FETCH_HEAD
[ -d voting-infra-local ] || git clone -q "https://github.com/$OWNER/voting-infra-local.git"
git -C voting-infra-local pull -q --ff-only
# The copy, under the name the scenarios and the agent expect (../voting-gitops next to ai-sre-agent).
# -c applies the deploy key to the clone itself, and keeps it in the clone's config for the scenarios' pushes.
[ -d voting-gitops ] || git clone -q -c core.sshCommand="ssh -i ~/.ssh/gitops -o IdentitiesOnly=yes"   "git@github.com:$GITOPS_REPO.git" voting-gitops
git -C voting-gitops config user.name "$GIT_NAME"
git -C voting-gitops config user.email "$GIT_EMAIL"
git -C voting-gitops fetch -q origin && git -C voting-gitops checkout -q -B "$GITOPS_BRANCH" "origin/$GITOPS_BRANCH"
cp ~/agent.env ai-sre-agent/.env

cd ai-sre-agent
uv sync -q
GITOPS_REPO_URL=https://github.com/$GITOPS_REPO.git GITOPS_REVISION=$GITOPS_BRANCH ../voting-infra-local/scripts/up.sh
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
echo "stand ready on $GITOPS_BRANCH"
EOF
)

prepare_one() {
  local n=$1 tmp
  tmp=$(mktemp -d)
  for key in "${ENV_KEYS[@]}"; do grep -E "^$key=" .env | tail -1 >> "$tmp/agent.env" || true; done
  printf 'SLACK_BOT_TOKEN=\nSLACK_CHANNEL=\n' >> "$tmp/agent.env"
  # GITOPS_BRANCH is read by the scenario scripts and by the agent's gitops_log tool.
  printf 'export %s\n' "$(printf '%q ' GITOPS_BRANCH="lab-$n" MLFLOW_DISABLE_AGENT_HINT=1 AGENT_REF="$AGENT_REF" \
    OWNER="$OWNER" GITOPS_REPO="$GITOPS_REPO" GIT_NAME="$(git -C "$GITOPS_DIR" config user.name)" \
    GIT_EMAIL="$(git -C "$GITOPS_DIR" config user.email)")" > "$tmp/stand.env"
  printf '%s\n' "$PREPARE" > "$tmp/prepare.sh"
  copy_to "$n" "$tmp/agent.env" agent.env
  copy_to "$n" "$tmp/stand.env" stand.env
  copy_to "$n" "$tmp/prepare.sh" prepare.sh
  copy_to "$n" "$GITOPS_KEY" .ssh/gitops
  rm -rf "$tmp"
  on "$n" "rm -f ~/prepare.exit; tmux kill-session -t prepare 2> /dev/null;
    tmux new-session -d -s prepare 'bash ~/prepare.sh > ~/prepare.log 2>&1; echo \$? > ~/prepare.exit'"
  log "stand $n: preparing in tmux (cloud/stands.sh status)"
}

cmd_prepare() {
  [ -f .env ] || { echo "no .env in $(pwd)" >&2; exit 1; }
  if ! "$GH" repo view "$GITOPS_REPO" > /dev/null 2>&1; then
    "$GH" repo create "$GITOPS_REPO" --public \
      --description "Copy of voting-gitops for the ai-sre-agent backtest stands: they commit breakages here"
    # Its lint workflow would run on every breakage commit.
    "$GH" api -X PUT "repos/$GITOPS_REPO/actions/permissions" -F enabled=false
    log "created $GITOPS_REPO (Actions off)"
  fi
  deploy_key
  git -C "$GITOPS_DIR" fetch -q origin lab
  local n url=https://github.com/$GITOPS_REPO.git
  for n in $(stand_numbers "$@"); do
    # A fresh lab-N from lab of the original: leftovers of an earlier session's scenarios must not carry over.
    # Pushed by URL: the remotes of the laptop's clone stay as they are.
    git -C "$GITOPS_DIR" push -q --force "$url" "origin/lab:refs/heads/lab-$n"
    log "stand $n: lab-$n = lab ($(git -C "$GITOPS_DIR" rev-parse --short origin/lab))"
    prepare_one "$n"
  done
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
until [ -f ~/prepare.exit ]; do sleep 30; done
[ "\$(cat ~/prepare.exit)" = 0 ] || { echo "the stand did not come up, see ~/prepare.log"; exit 1; }
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
    on "$n" 'if [ -f ~/prepare.exit ]; then p="exit $(cat ~/prepare.exit)";
      elif [ -f ~/prepare.log ]; then p=running; else p="not started"; fi
      b=$(tmux has-session -t bt 2> /dev/null && echo running || echo idle);
      echo "--- prepare: $p, backtest: $b"; tail -n 2 ~/prepare.log 2> /dev/null; tail -n 4 ~/backtest.log 2> /dev/null; true' |
      sed "1s/^---/--- stand $n/" || echo "--- stand $n: no answer"
  done
}

cmd_collect() {
  local n
  mkdir -p "$LOGS"
  for n in $(stand_numbers); do
    # No rsync in Git Bash: a tar stream. Result directories are named by time, so nothing local is overwritten.
    on "$n" 'cd ai-sre-agent && mkdir -p backtest/results audit && tar -cf - backtest/results audit' | tar -xf -
    on "$n" 'cat ~/prepare.log ~/backtest.log 2> /dev/null' > "$LOGS/stand-$n.log" || true
    log "stand $n collected (log $LOGS/stand-$n.log)"
  done
}

cmd_down() {
  session
  local count n
  count=$(ips 2> /dev/null | wc -l) || true
  [ "${count:-0}" -gt 0 ] || count=$STANDS
  tf init -input=false > /dev/null
  # shellcheck disable=SC2046
  tf destroy $(tf_vars "$count" 127.0.0.1/32) -var ssh_public_key="$(cat "$KEY.pub")"
  for n in $(seq 1 "$count"); do
    git -C "$GITOPS_DIR" push -q "https://github.com/$GITOPS_REPO.git" --delete "lab-$n" 2> /dev/null &&
      log "deleted branch lab-$n of $GITOPS_REPO" || true
  done
  if [ -s "$KEY_ID_FILE" ]; then
    "$GH" api -X DELETE "repos/$GITOPS_REPO/keys/$(cat "$KEY_ID_FILE")" && log "deploy key removed"
    rm -f "$KEY_ID_FILE"
  fi
  rm -f "$KNOWN_HOSTS"
}

cmd_leftovers() {
  gcloud compute instances list --project "$PROJECT" --filter=labels.project=ai-sre-agent --format='value(name)'
  gcloud compute disks list --project "$PROJECT" --filter=labels.project=ai-sre-agent --format='value(name)'
  gcloud compute networks list --project "$PROJECT" --filter=name=ai-sre-stands --format='value(name)'
}

case "${1:-}" in
  plan | up | prepare | run | status | collect | down | leftovers)
    cmd=$1
    shift
    "cmd_$cmd" "$@"
    ;;
  ssh) on "$2" ;;
  *)
    sed -n '2,20p' "$0" >&2
    exit 2
    ;;
esac
