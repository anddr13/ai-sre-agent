"""The runbook corpus, how retrieved runbooks reach the model, and RAG failing without breaking the agent."""

import json
from pathlib import Path

from test_investigator import PAYLOAD, FakeTools, ScriptedLlm, answer_reply, audit_text, settings

from ai_sre_agent import rag
from ai_sre_agent.audit import Audit
from ai_sre_agent.investigator import investigate, retrieve

ALERTS = {
    "VotingPodNotStarting", "VotingHttp5xxRate", "KafkaUnderReplicatedPartitions", "PostgresPrimaryFailover",
    "PostgresConnectionsHigh", "PostgresReplicationLag", "ContainerOOMKilled", "VotingApiLatencyHigh",
}  # fmt: skip


def test_corpus_is_one_runbook_per_alert_cut_at_sections() -> None:
    sections = rag.corpus()
    assert {s.source for s in sections} == ALERTS
    connections = [s for s in sections if s.source == "PostgresConnectionsHigh"]
    assert [s.heading for s in connections] == ["Symptom", "What to check", "Typical causes", "Mitigation"]
    assert connections[0].content.startswith("# PostgresConnectionsHigh")
    assert connections[2].content.startswith("## Typical causes")
    # Every section fits the 512 tokens of bge-small (~4 characters per token).
    assert max(len(s.text_to_embed) for s in sections) < 1800


def test_section_hash_changes_with_the_text(tmp_path: Path) -> None:
    path = tmp_path / "X.md"
    path.write_text("# X\n\nsymptom\n\n## Mitigation\n\nrevert\n", encoding="utf-8")
    before = rag.sections(path)
    path.write_text("# X\n\nsymptom\n\n## Mitigation\n\nrestart\n", encoding="utf-8")
    after = rag.sections(path)
    assert before[0].sha == after[0].sha and before[1].sha != after[1].sha


def test_context_marks_runbooks_as_background_not_evidence() -> None:
    text = rag.context([rag.Runbook("PostgresConnectionsHigh", 0.81, "# PostgresConnectionsHigh\n...")])
    assert "not evidence" in text and "--- runbook PostgresConnectionsHigh (similarity 0.81) ---" in text
    assert rag.context([]) == ""


async def test_runbooks_go_into_the_first_message_and_the_audit(tmp_path: Path) -> None:
    llm = ScriptedLlm([answer_reply()])
    runbooks = [rag.Runbook("VotingPodNotStarting", 0.9, "# VotingPodNotStarting\ncheck the image tag")]
    inv = await investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"), runbooks)

    first = llm.requests[0][0][1]["content"]
    assert first.index("Alert VotingPodNotStarting") < first.index("check the image tag") < first.index("Investigate.")
    records = [json.loads(line) for line in audit_text(inv.audit_path).splitlines()]
    assert {"event": "runbooks"}.items() <= records[1].items()
    assert records[1]["retrieved"] == [{"source": "VotingPodNotStarting", "score": 0.9}]


async def test_without_runbooks_the_first_message_is_unchanged(tmp_path: Path) -> None:
    llm = ScriptedLlm([answer_reply()])
    await investigate(PAYLOAD, settings(tmp_path), llm, FakeTools(), Audit(str(tmp_path), "x"))
    assert "runbook" not in llm.requests[0][0][1]["content"].lower().replace("runbook_url", "")


async def test_retrieval_is_off_without_a_database_and_survives_a_dead_one(tmp_path: Path) -> None:
    audit = Audit(str(tmp_path), "x")
    assert await retrieve(PAYLOAD, settings(tmp_path), audit) == []
    dead = settings(tmp_path, rag_database_url="postgresql://u:p@127.0.0.1:9/agent")
    assert await retrieve(PAYLOAD, dead, audit) == []
    assert '"event": "runbooks"' in audit_text(str(audit.path)) and "error" in audit_text(str(audit.path))
