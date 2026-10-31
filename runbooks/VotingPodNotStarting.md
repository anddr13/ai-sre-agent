# VotingPodNotStarting

**Symptom.** A container in the `voting` namespace has been waiting for more than 2 minutes in
`ImagePullBackOff`, `ErrImagePull`, `InvalidImageName`, `CrashLoopBackOff` or `CreateContainerConfigError`.
The old ReplicaSet usually keeps serving, so users may notice nothing yet, but the rollout is stuck.

## What to check

1. Which pod, container and reason: the alert labels, or
   `kube_pod_container_status_waiting_reason{namespace="voting"} > 0`.
2. Events of the pod: `Failed to pull image ... not found`, `Back-off restarting failed container`,
   `secret "..." not found`.
3. The image of the stuck pod vs. the running ones: `kubectl -n voting get deploy <name> -o yaml`, `.spec.template.spec.containers[].image`.
4. What changed: Argo CD history of the `voting` application (sync revision, time) and `git log` of voting-gitops
   around the time the alert started. A new image tag right before the alert is the prime suspect.
5. For `CrashLoopBackOff`: the logs of the previous container (`{namespace="voting", pod="<pod>"}` in Loki),
   usually the last lines before the exit.

## Typical causes

- Image tag that does not exist in the registry (typo, CI did not push, wrong registry).
- Private image without pull credentials.
- The app crashes at start: missing or wrong env variable, unreachable dependency (PostgreSQL, Kafka, Redis).
- A referenced Secret or ConfigMap does not exist (`CreateContainerConfigError`).

## Mitigation

- Bad tag or bad release: roll back the `voting` application to the previous good revision
  (revert the commit in voting-gitops that changed `image.tag`, or Argo CD rollback to revision N).
- Crash on start because of a dependency: fix the dependency first; the pod recovers by itself.
- Missing Secret: restore it (for PostgreSQL credentials it is created by CloudNativePG as `voting-pg-app`).
