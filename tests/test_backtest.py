"""Scoring of the backtest: which hypothesis matched the known cause, and the triage label."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from ai_sre_agent.backtest import ALL, SCENARIOS_DIR, score, summary
from ai_sre_agent.investigator import Investigation


def inv(root_cause: str, alternatives: list[str] | None = None, triage: str = "wake", **extra: Any) -> Investigation:
    values: dict[str, Any] = {
        "investigation_id": "i",
        "alertname": "A",
        "summary": extra.pop("summary", ""),
        "root_cause": root_cause,
        "confidence": "high",
        "mitigation": "",
        "triage": triage,
        "alternatives": alternatives or [],
        "evidence": [],
        "stopped_by": "answer",
        "model": "m",
        "steps": 1,
        "tool_calls": 1,
        "tokens": 1,
        "cost_usd": 0.0,
        "duration_s": 1.0,
        "audit_path": "",
    }
    return Investigation(**(values | extra))


BAD_DEPLOY = {"triage": "wake", "match": ["ebac3bd", "image|tag|pull"]}


def test_top1() -> None:
    assert score(inv("Release ebac3bd set an image tag that does not exist"), BAD_DEPLOY) == (1, True)


def test_top3_when_the_right_cause_is_second() -> None:
    answer = inv("The registry is down", ["Revision ebac3bd points at a missing image tag"])
    assert score(answer, BAD_DEPLOY) == (2, True)


def test_all_patterns_must_match_one_hypothesis() -> None:
    # The revision is in one hypothesis and the image in another: neither alone is the cause.
    assert score(inv("ebac3bd changed something", ["an image pull problem"]), BAD_DEPLOY) == (None, True)


def test_summary_does_not_count() -> None:
    # A summary can hedge over several causes ("... may also contribute"); only the ranked hypotheses are scored.
    answer = inv("image tag missing from the registry", summary="caused by release ebac3bd")
    assert score(answer, BAD_DEPLOY)[0] is None


def test_noise_scenario_scores_the_label_only() -> None:
    expected = {"triage": "noise", "match": []}
    assert score(inv("a burst of traffic", triage="noise"), expected) == (1, True)
    assert score(inv("the release broke latency", triage="wake"), expected) == (None, False)


def test_triage_alternatives() -> None:
    expected = {"triage": "wake|morning", "match": ["replica", "lag"]}
    assert score(inv("replica lag", triage="morning"), expected) == (1, True)
    assert score(inv("replica lag", triage="noise"), expected) == (1, False)


@pytest.mark.parametrize("name", ALL)
def test_every_scenario_has_scripts_and_scoring_rules(name: str) -> None:
    directory = SCENARIOS_DIR / name
    assert (directory / "break.sh").exists() and (directory / "restore.sh").exists()
    expected = yaml.safe_load((directory / "expected.yaml").read_text(encoding="utf-8"))
    assert expected["alert"] and expected["triage"]
    assert expected["triage"] == "noise" or expected["match"]


def test_summary_table(tmp_path: Path) -> None:
    from ai_sre_agent.backtest import Result

    result = Result("01-bad-deploy", 1, "A", "wake", 1, True, True, "wake", True, "high", ["x"], 75.0, 15.0,
                    100, 0.001, 2, 4, "answer", "m", "p", "a")  # fmt: skip
    text = summary([result], "test")
    assert "**Top-1**: 1/1" in text and "| 01-bad-deploy #1 |" in text
