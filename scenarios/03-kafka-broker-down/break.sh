#!/usr/bin/env bash
# Scenario 3, Kafka broker down: one of the three brokers hangs under load.
#
# The plan said "delete the broker pod", but on this stand Strimzi has the broker back and in sync within
# ~30 s, before any sensible alert fires (tried with and without load). So the broker's JVM is frozen with
# SIGSTOP from the kind node instead: the pod stays Running and even passes Strimzi's liveness probe (it only
# checks that a java process exists), but the broker drops out of every ISR. Like a hung broker or a node that
# stopped responding. restore.sh sends SIGCONT.
source "$(dirname "$0")/../lib.sh"
S=03-kafka-broker-down
POD=${POD:-voting-dual-role-1}

load_start $S 100 15m
sleep 20
init_pid=$(container_pid "$POD" kafka)
java_pid=$(docker exec "$NODE" pgrep -P "$init_pid" java)
docker exec "$NODE" kill -STOP "$java_pid"
log "broker $POD frozen (java pid $java_pid on the node)"
save_state $S pid "$java_pid"
save_state $S pod "$POD"

sed -e "s/{{pod}}/$POD/g" "$(dirname "$0")/expected.yaml" > "$STATE_DIR/$S.expected.yaml"
log "expected answer: $STATE_DIR/$S.expected.yaml"

wait_alert KafkaUnderReplicatedPartitions firing 420
