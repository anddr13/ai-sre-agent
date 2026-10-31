# KafkaUnderReplicatedPartitions

**Symptom.** Partitions of a topic in the `voting` Kafka cluster (Strimzi, 3 KRaft nodes, replication factor 3,
`min.insync.replicas=2`) have fewer in-sync replicas than replicas. With one broker missing producers still
work; with two missing, `acks=all` writes fail and vote-api returns 5xx.

## What to check

1. Which topics and how many partitions: `kafka_topic_partition_under_replicated_partition{namespace="voting"} > 0`.
2. Are all brokers running: pods `voting-dual-role-*` (status, restarts, events). A pod being recreated or
   stuck `Pending` (PVC, node resources) is the usual reason.
3. Broker logs in Loki: `{namespace="voting", pod=~"voting-dual-role-.*"}`, look for shutdown, OOM, disk errors.
4. In-sync replicas per partition: `kafka_topic_partition_in_sync_replica{topic="votes"}` vs `kafka_topic_partition_replicas`.
5. Impact on consumers: consumer group lag `kafka_consumergroup_lag{consumergroup="vote-workers"}`, and the
   `VotingHttp5xxRate` alert for producers.

## Typical causes

- A broker pod was deleted, evicted or OOMKilled and is restarting.
- A broker cannot start: PVC not bound, not enough memory on the node.
- A slow broker (disk, GC) falls out of the ISR.

## Mitigation

- A restarting broker usually catches up by itself within minutes; watch the metric return to 0.
- Broker stuck: fix the cause (PVC, memory) so the pod can start; do not delete PVCs of brokers.
- If two brokers are gone, producers fail: restoring brokers is the only real fix.
