"""The webhook service: answers at once, investigates in the background, de-duplicates, threads resolutions."""

import asyncio
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ai_sre_agent.config import Settings
from ai_sre_agent.investigator import Evidence, Investigation
from ai_sre_agent.service import create_app
from ai_sre_agent.slack import blocks

FIRING = {
    "status": "firing",
    "groupKey": "g1",
    "alerts": [
        {"status": "firing", "labels": {"alertname": "A"}, "fingerprint": "f1", "startsAt": "2026-10-31T10:00:00Z"}
    ],
}


def result(**overrides: Any) -> Investigation:
    values: dict[str, Any] = {
        "investigation_id": "abc",
        "alertname": "A",
        "summary": "broken",
        "root_cause": "cause",
        "confidence": "high",
        "mitigation": "revert",
        "noise": False,
        "evidence": [Evidence(1, "k8s_events", {"namespace": "voting"}, "pull failed", '{"reason": "x"}')],
        "stopped_by": "answer",
        "model": "m",
        "steps": 2,
        "tool_calls": 1,
        "tokens": 100,
        "cost_usd": 0.001,
        "duration_s": 3.0,
        "audit_path": "a.jsonl",
        "alert_started_at": "2026-10-31T10:00:00Z",
    }
    return Investigation(**(values | overrides))


class FakeSlack:
    enabled = True

    def __init__(self) -> None:
        self.posts: list[tuple[str, str | None]] = []

    async def post(self, text: str, blocks: Any = None, thread_ts: str | None = None) -> str:
        self.posts.append((text, thread_ts))
        return "ts-1"

    async def post_investigation(self, inv: Investigation) -> str:
        return await self.post(f"{inv.alertname}: {inv.summary}")


def make(tmp_path: Path) -> tuple[TestClient, list[dict[str, Any]], FakeSlack]:
    calls: list[dict[str, Any]] = []

    async def fake_investigate(payload: dict[str, Any], _: Settings) -> Investigation:
        calls.append(payload)
        return result()

    slack = FakeSlack()
    app = create_app(Settings(audit_dir=str(tmp_path)), fake_investigate, slack)  # type: ignore[arg-type]
    return TestClient(app), calls, slack


def drain(client: TestClient) -> None:
    async def wait() -> None:
        await asyncio.gather(*list(client.app.state.tasks))  # type: ignore[attr-defined]

    client.portal.call(wait)  # type: ignore[union-attr]


def test_firing_alert_is_investigated_once_and_posted(tmp_path: Path) -> None:
    client, calls, slack = make(tmp_path)
    with client:
        assert client.post("/alertmanager", json=FIRING).status_code == 202
        drain(client)
        assert client.post("/alertmanager", json=FIRING).json() == {"status": "duplicate"}
        drain(client)
    assert len(calls) == 1
    assert slack.posts == [("A: broken", None)]


def test_resolved_goes_to_the_thread(tmp_path: Path) -> None:
    client, _, slack = make(tmp_path)
    with client:
        client.post("/alertmanager", json=FIRING)
        drain(client)
        client.post("/alertmanager", json=FIRING | {"status": "resolved"})
    assert slack.posts[-1] == (":white_check_mark: Resolved: A", "ts-1")


def test_healthz(tmp_path: Path) -> None:
    client, _, _ = make(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}


def test_slack_blocks_show_the_call_and_its_result() -> None:
    text = str(blocks(result()))
    assert 'k8s_events(namespace="voting")' in text
    assert '{"reason": "x"}' in text
    assert "read-only, nothing was changed" in text


def test_slack_blocks_for_a_failed_investigation() -> None:
    text = str(blocks(result(root_cause="", error="ConnectionError: down", evidence=[])))
    assert "Investigation failed" in text
