"""Investigators + verifier with a scripted LLM per role: evidence checks, the verifier's say, limits."""

import asyncio
import json
from pathlib import Path
from typing import Any

from test_investigator import PAYLOAD, FakeTools, answer_reply, audit_events, audit_text, settings, tool_reply

from ai_sre_agent import team
from ai_sre_agent.audit import Audit
from ai_sre_agent.investigator import Reply

EMPTY = {"hypotheses": [], "impact": "no errors"}


def hypothesis(cause: str, *calls: int) -> dict[str, Any]:
    return {
        "cause": cause,
        "evidence": [{"call": c, "finding": f"shows {cause}"} for c in calls],
        "mitigation": f"undo {cause}",
    }


def verdict(ranking: list[str], rejected: tuple[str, ...] = (), **extra: Any) -> dict[str, Any]:
    verdicts = [{"id": i, "supported": True, "reason": "shown"} for i in ranking]
    verdicts += [{"id": i, "supported": False, "reason": "not shown"} for i in rejected]
    return {
        "verdicts": verdicts,
        "ranking": ranking,
        "summary": "verified",
        "confidence": "high",
        "mitigation": "git revert abc123",
        "triage": "wake",
        **extra,
    }


class RoleLlm:
    """Replies by role (the investigator's focus or the verifier), whatever order the parallel calls come in."""

    model = "scripted"

    def __init__(self, replies: dict[str, list[Reply]], delay: float = 0.0):
        self.replies = replies
        self.delay = delay
        self.requests: dict[str, list[tuple[list[dict[str, Any]], list[dict[str, Any]], bool]]] = {}
        self.in_flight = self.max_in_flight = 0

    def role(self, system: str) -> str:
        if system == team.VERIFIER_PROMPT:
            return "verifier"
        return next(name for name, focus in team.FOCUS.items() if focus in system)

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], allow_tools: bool) -> Reply:
        role = self.role(messages[0]["content"])
        self.requests.setdefault(role, []).append(([dict(m) for m in messages], tools, allow_tools))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delay)
            reply = self.replies[role].pop(0)
        finally:
            self.in_flight -= 1
        if isinstance(reply, Exception):
            raise reply
        return reply


def scripted(verifier: list[Any] | None = None) -> dict[str, list[Any]]:
    """changes: one call, a cited hypothesis; resources: nothing; dependencies: one call, one cited and one not."""
    return {
        "changes": [tool_reply('{"namespace": "voting"}'), answer_reply({"hypotheses": [hypothesis("image tag", 1)]})],
        "resources": [answer_reply(EMPTY)],
        "dependencies": [
            tool_reply('{"namespace": "voting"}'),
            answer_reply(
                {"hypotheses": [hypothesis("redis down", 1), hypothesis("kafka down", 5)], "impact": "5xx since 10:00"}
            ),
        ],
        "verifier": verifier if verifier is not None else [answer_reply(verdict(["H1"], rejected=("H2",)))],
    }


async def test_verified_hypothesis_wins_with_renumbered_evidence(tmp_path: Path) -> None:
    llm = RoleLlm(scripted())
    inv = await team.investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert inv.root_cause == "image tag" and inv.alternatives == []
    assert (inv.confidence, inv.triage, inv.summary, inv.stopped_by) == ("high", "wake", "verified", "answer")
    assert [e.call for e in inv.evidence] == [1]
    assert inv.tool_calls == 2 and inv.prompt_version == team.PROMPT_VERSION
    assert inv.tokens == 150 + 50 + 150 + 50  # three investigators and the verifier
    # The verifier sees the cited results, renumbered across investigators, and nothing that cited no real call.
    seen = llm.requests["verifier"][0][0][1]["content"]
    assert "H1 (changes): image tag" in seen and "H2 (dependencies): redis down" in seen
    assert "[call 2] k8s_events" in seen and "ImagePullBackOff" in seen
    assert "kafka down" not in seen
    assert "5xx since 10:00" in seen
    # The verifier has no tools.
    assert llm.requests["verifier"][0][1:] == ([], False)
    assert {"hypotheses", "verdict", "result"} <= set(audit_events(inv.audit_path))


async def test_rejected_by_the_verifier_means_no_cause(tmp_path: Path) -> None:
    llm = RoleLlm(scripted([answer_reply(verdict([], rejected=("H1", "H2"), summary="cause not established"))]))
    inv = await team.investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert inv.root_cause == "" and inv.hypotheses == [] and inv.evidence == []
    assert inv.confidence == "low"  # whatever the verifier said: nothing it supports
    assert inv.summary == "cause not established"


async def test_ranking_keeps_only_supported_known_ids(tmp_path: Path) -> None:
    ranking = verdict(["H2"], rejected=("H1",))
    ranking["ranking"] = ["H1", "H9", "H2"]  # H1 was rejected, H9 does not exist
    inv = await team.investigate(
        PAYLOAD, settings(tmp_path), RoleLlm(scripted([answer_reply(ranking)])), FakeTools(), Audit(str(tmp_path), "x")
    )
    assert inv.hypotheses == ["redis down"]
    assert [e.call for e in inv.evidence] == [2]


async def test_no_evidence_no_verifier(tmp_path: Path) -> None:
    replies = {name: [answer_reply(EMPTY)] for name in team.FOCUS} | {"verifier": []}
    llm = RoleLlm(replies)
    inv = await team.investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert "verifier" not in llm.requests
    assert (inv.root_cause, inv.confidence, inv.triage) == ("", "low", "wake")
    assert inv.summary == "No cause supported by evidence"


async def test_verifier_failure_keeps_the_evidence_backed_hypotheses_at_low_confidence(tmp_path: Path) -> None:
    llm = RoleLlm(scripted([RuntimeError("endpoint down")]))
    inv = await team.investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))

    assert inv.hypotheses == ["image tag", "redis down"]
    assert inv.confidence == "low" and inv.triage == "wake"
    assert "verifier: RuntimeError: endpoint down" in inv.error
    assert inv.stopped_by == "answer"  # there is an answer, only unverified


async def test_investigator_budget_is_its_own(tmp_path: Path) -> None:
    replies = scripted()
    replies["changes"] = [tool_reply("{}"), answer_reply({"hypotheses": [hypothesis("x", 1)]})]
    llm = RoleLlm(replies)
    await team.investigate(
        PAYLOAD, settings(tmp_path, investigator_max_steps=2), llm, FakeTools(), Audit(str(tmp_path), "x")
    )
    # The second turn is the last one: no tools, answer now.
    assert [allow for _, _, allow in llm.requests["changes"]] == [True, False]


async def test_parallel_investigators_are_limited(tmp_path: Path) -> None:
    for limit, expected in ((1, 1), (3, 3)):
        llm = RoleLlm({name: [answer_reply(EMPTY)] for name in team.FOCUS}, delay=0.05)
        await team.investigate(
            PAYLOAD,
            settings(tmp_path, max_parallel_investigators=limit),
            llm,
            FakeTools(),
            Audit(str(tmp_path), "x"),
        )
        assert llm.max_in_flight == expected


async def test_audit_tags_the_investigator(tmp_path: Path) -> None:
    inv = await team.investigate(
        PAYLOAD, settings(tmp_path), RoleLlm(scripted()), FakeTools(), Audit(str(tmp_path), "x")
    )
    records = [json.loads(line) for line in audit_text(inv.audit_path).splitlines()]
    assert {r.get("agent") for r in records if r["event"] in ("llm", "tool")} == {*team.FOCUS, "verifier"}
