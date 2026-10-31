#!/usr/bin/env bash
# Scenario 3, restore: resume the frozen broker and wait until every partition is in sync again.
source "$(dirname "$0")/../lib.sh"
S=03-kafka-broker-down

pid=$(load_state $S pid)
pod=$(load_state $S pod)
[ -n "$pid" ] || { echo "No break recorded for $S." >&2; exit 1; }

# The pid is only valid while that container lives; if it was restarted meanwhile there is nothing to resume.
docker exec "$NODE" kill -CONT "$pid" 2> /dev/null && log "broker $pod resumed" || log "pid $pid is gone, $pod was restarted"
load_stop $S
kubectl -n "$NS" wait pod "$pod" --for=condition=Ready --timeout=300s > /dev/null
wait_alert KafkaUnderReplicatedPartitions resolved 420
clear_state $S
