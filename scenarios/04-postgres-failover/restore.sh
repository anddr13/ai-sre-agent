#!/usr/bin/env bash
# Scenario 4, restore: nothing to undo, CloudNativePG heals by itself. Wait until both instances are ready
# (the old primary rejoins as a replica) and the alert's 5-minute window has passed.
source "$(dirname "$0")/../lib.sh"
S=04-postgres-failover

load_stop $S
wait_pg_healthy 300
wait_alert PostgresPrimaryFailover resolved 420
clear_state $S
