"""The agent loop with a scripted LLM and fake tools: budgets, redaction, evidence, audit."""

import json
from pathlib import Path
from typing import Any

from ai_sre_agent.audit import Audit
from ai_sre_agent.config import Settings
from ai_sre_agent.investigator import Reply, ToolCall, describe_alerts, investigate, parse_action

PAYLOAD = {
    "status": "firing",
    "groupKey": '{}/{stand="voting"}:{alertname="VotingPodNotStarting"}',
    "commonLabels": {"alertname": "VotingPodNotStarting"},
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "VotingPodNotStarting", "namespace": "voting", "pod": "migrate-x"},
            "annotations": {"summary": "migrate-x cannot start", "runbook_url": "https://example/rb.md"},
            "startsAt": "2026-10-31T10:00:00Z",
            "fingerprint": "abc",
        },
        {"status": "resolved", "labels": {"alertname": "Old"}, "annotations": {}, "fingerprint": "def"},
    ],
}

ANSWER = {
    "summary": "Release abc123 points at an image tag that does not exist",
    "root_cause": "image.tag changed by revision abc123",
    "confidence": "high",
    "evidence": [{"call": 1, "finding": "ImagePullBackOff"}, {"call": 7, "finding": "made up"}],
    "mitigation": "git revert abc123 on branch lab",
    "alternatives": ["the registry is down"],
    "triage": "wake",
}


class ScriptedLlm:
    model = "scripted"

    def __init__(self, replies: list[Reply]):
        self.replies = replies
        self.requests: list[tuple[list[dict[str, Any]], bool]] = []

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], allow_tools: bool) -> Reply:
        self.requests.append(([dict(m) for m in messages], allow_tools))
        return self.replies.pop(0)


class FakeTools:
    def __init__(self, result: str = '{"reason": "ImagePullBackOff", "podIP": "10.244.0.9"}'):
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def specs(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": "k8s_events", "description": "", "parameters": {}}}]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        self.calls.append((name, arguments))
        return False, self.result


def tool_reply(*arguments: str) -> Reply:
    return Reply("", [ToolCall(f"id{i}", "k8s_events", a) for i, a in enumerate(arguments)], tokens=100, cost=0.001)


def answer_reply(answer: dict[str, Any] | str = ANSWER) -> Reply:
    text = answer if isinstance(answer, str) else json.dumps(answer)
    return Reply(text, [], tokens=50, cost=0.0005)


def audit_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def audit_events(path: str) -> list[str]:
    return [json.loads(line)["event"] for line in audit_text(path).splitlines()]


def settings(tmp_path: Path, **overrides: Any) -> Settings:
    return Settings(audit_dir=str(tmp_path), **overrides)


def test_describe_alerts_lists_only_firing() -> None:
    text = describe_alerts(PAYLOAD)
    assert "VotingPodNotStarting firing since 2026-10-31T10:00:00Z" in text
    assert "runbook_url: https://example/rb.md" in text
    assert "Old" not in text


async def test_tool_call_then_answer(tmp_path: Path) -> None:
    llm = ScriptedLlm([tool_reply('{"namespace": "voting"}'), answer_reply()])
    tools = FakeTools()
    inv = await investigate(PAYLOAD, settings(tmp_path), llm, tools, Audit(str(tmp_path), "VotingPodNotStarting"))

    assert tools.calls == [("k8s_events", {"namespace": "voting"})]
    assert inv.stopped_by == "answer"
    assert inv.confidence == "high"
    assert inv.hypotheses == [ANSWER["root_cause"], "the registry is down"]
    assert inv.triage == "wake" and not inv.noise
    assert (inv.steps, inv.tool_calls, inv.tokens) == (2, 1, 150)
    # Evidence only for calls that happened, with the real arguments and result.
    assert [e.call for e in inv.evidence] == [1]
    assert inv.evidence[0].arguments == {"namespace": "voting"}
    assert "ImagePullBackOff" in inv.evidence[0].result_excerpt


async def test_tool_results_are_redacted_before_the_llm(tmp_path: Path) -> None:
    llm = ScriptedLlm([tool_reply('{"namespace": "voting"}'), answer_reply()])
    tools = FakeTools('{"podIP": "10.244.0.9", "env": "PGPASSWORD=hunter2"}')
    inv = await investigate(PAYLOAD, settings(tmp_path), llm, tools, Audit(str(tmp_path), "x"))

    seen_by_llm = json.dumps(llm.requests[-1][0])
    assert "10.244.0.9" not in seen_by_llm and "<ip-1>" in seen_by_llm
    assert "hunter2" not in seen_by_llm
    assert "hunter2" not in audit_text(inv.audit_path)


async def test_step_limit_forces_a_final_answer_without_tools(tmp_path: Path) -> None:
    llm = ScriptedLlm([tool_reply("{}"), tool_reply("{}"), answer_reply()])
    inv = await investigate(PAYLOAD, settings(tmp_path, max_steps=3), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert [allow for _, allow in llm.requests] == [True, True, False]
    assert inv.stopped_by == "max_steps"
    assert inv.summary == ANSWER["summary"]


async def test_token_limit_forces_a_final_answer(tmp_path: Path) -> None:
    llm = ScriptedLlm([tool_reply("{}"), answer_reply()])
    inv = await investigate(PAYLOAD, settings(tmp_path, max_tokens=100), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert [allow for _, allow in llm.requests] == [True, False]
    assert inv.stopped_by == "max_tokens"


async def test_bad_tool_arguments_are_reported_to_the_model(tmp_path: Path) -> None:
    llm = ScriptedLlm([tool_reply("not json"), answer_reply()])
    tools = FakeTools()
    await investigate(PAYLOAD, settings(tmp_path), llm, tools, Audit(str(tmp_path), "x"))

    assert tools.calls == []
    tool_message = llm.requests[-1][0][-1]
    assert tool_message["role"] == "tool" and "ERROR invalid arguments" in tool_message["content"]


async def test_prose_answer_gets_one_more_chance_and_think_blocks_are_ignored(tmp_path: Path) -> None:
    llm = ScriptedLlm(
        [answer_reply("I think it is the image."), answer_reply("<think>hmm {x}</think>" + json.dumps(ANSWER))]
    )
    inv = await investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert inv.stopped_by == "answer"
    assert inv.root_cause == ANSWER["root_cause"]


async def test_llm_failure_still_returns_a_result_and_audit(tmp_path: Path) -> None:
    class BrokenLlm:
        model = "broken"

        async def complete(self, *_: Any, **__: Any) -> Reply:
            raise ConnectionError("endpoint down")

    inv = await investigate(PAYLOAD, settings(tmp_path), BrokenLlm(), FakeTools(), Audit(str(tmp_path), "x"))

    assert inv.stopped_by == "error"
    assert "endpoint down" in inv.error
    assert audit_events(inv.audit_path) == ["alert", "start", "error", "result"]


async def test_audit_records_every_step(tmp_path: Path) -> None:
    llm = ScriptedLlm([tool_reply('{"namespace": "voting"}'), answer_reply()])
    inv = await investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert audit_events(inv.audit_path) == ["alert", "start", "llm", "tool", "llm", "result"]


async def test_unknown_triage_defaults_to_wake(tmp_path: Path) -> None:
    llm = ScriptedLlm([answer_reply(ANSWER | {"triage": "maybe"})])
    inv = await investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))
    assert inv.triage == "wake"


def test_only_allowed_actions_survive() -> None:
    assert parse_action({"type": "revert", "sha": "ABC1234"}) == {"type": "revert", "sha": "abc1234"}
    assert parse_action({"type": "restart_pod", "pod": "voting-pg-2"}) == {"type": "restart_pod", "pod": "voting-pg-2"}
    for bad in (
        {"type": "revert", "sha": "HEAD~1"},
        {"type": "revert", "sha": "abc; rm -rf /"},
        {"type": "restart_pod", "pod": "--all"},
        {"type": "exec", "command": "psql"},
        "revert abc1234",
        None,
    ):
        assert parse_action(bad) == {"type": "none"}


async def test_the_action_is_part_of_the_answer(tmp_path: Path) -> None:
    answer = ANSWER | {"action": {"type": "revert", "sha": "abc1234"}}
    inv = await investigate(
        PAYLOAD, settings(tmp_path), ScriptedLlm([answer_reply(answer)]), FakeTools(), Audit(str(tmp_path), "x")
    )
    assert inv.action == {"type": "revert", "sha": "abc1234"}
    inv = await investigate(
        PAYLOAD, settings(tmp_path), ScriptedLlm([answer_reply()]), FakeTools(), Audit(str(tmp_path), "x")
    )
    assert inv.action == {"type": "none"}
