"""The rule baseline with canned tool results."""

import json
from pathlib import Path
from typing import Any

from ai_sre_agent.audit import Audit
from ai_sre_agent.rules import investigate

LOG = {"commits_newest_first": [{"sha": "ebac3bd35866", "subject": "voting: release 395b4b4"}]}
POD = {"containers": [{"image": "ghcr.io/x/worker:395b4b4", "state": {"waiting": {"reason": "ImagePullBackOff"}}}]}
LAG = {
    "series": [
        {"labels": {"pod": "voting-pg-1"}, "value": [0, "3"]},
        {"labels": {"pod": "voting-pg-2"}, "value": [0, "95"]},
    ]
}


class CannedTools:
    def __init__(self, answers: dict[str, dict[str, Any]]):
        self.answers = answers
        self.calls: list[str] = []

    async def specs(self) -> list[dict[str, Any]]:
        return []

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        self.calls.append(name)
        return False, json.dumps(self.answers.get(name, {}))


def payload(alertname: str, **labels: str) -> dict[str, Any]:
    alert = {"status": "firing", "labels": {"alertname": alertname, **labels}, "startsAt": "2026-11-01T10:00:00Z"}
    return {"alerts": [alert]}


async def test_pod_not_starting_names_the_image_and_the_latest_release(tmp_path: Path) -> None:
    tools = CannedTools({"k8s_describe": POD, "gitops_log": LOG})
    inv = await investigate(
        payload("VotingPodNotStarting", namespace="voting", pod="migrate-x"), tools, Audit(str(tmp_path), "x")
    )
    assert "ImagePullBackOff" in inv.root_cause and "ebac3bd" in inv.root_cause
    assert tools.calls == ["k8s_describe", "gitops_log"]
    assert inv.model == "rules" and inv.tokens == 0
    assert inv.action == {"type": "revert", "sha": "ebac3bd"}


async def test_replica_lag_picks_the_worst_replica(tmp_path: Path) -> None:
    inv = await investigate(
        payload("PostgresReplicationLag"), CannedTools({"prometheus_query": LAG}), Audit(str(tmp_path), "x")
    )
    assert "voting-pg-2" in inv.root_cause
    assert inv.triage == "morning"


async def test_alert_without_a_playbook_is_triaged_by_severity(tmp_path: Path) -> None:
    inv = await investigate(
        payload("VotingApiLatencyHigh", severity="warning"), CannedTools({}), Audit(str(tmp_path), "x")
    )
    assert inv.triage == "morning"  # a rule cannot tell a latency blip from an incident


async def test_a_failing_tool_is_an_error_not_a_crash(tmp_path: Path) -> None:
    class Broken(CannedTools):
        async def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
            raise ConnectionError("down")

    inv = await investigate(payload("ContainerOOMKilled", container="redis"), Broken({}), Audit(str(tmp_path), "x"))
    assert inv.stopped_by == "error" and "down" in inv.error
