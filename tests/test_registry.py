"""Backtests into MLflow and the best configuration into the Prompt Registry."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import mlflow
import pytest

from ai_sre_agent import investigator, registry, team
from ai_sre_agent.backtest import Result


def result(scenario: str, top1: bool, confidence: str = "high") -> Result:
    return Result(scenario, 1, "A", "wake", 1 if top1 else None, top1, top1, "wake", True, confidence, ["x"], 60.0,
                  50.0, 100, 0.001, 2, 4, "answer", "m", "p", "a")  # fmt: skip


def backtest(root: Path, name: str, agent: str, top1: list[bool], **params: Any) -> Path:
    directory = root / name
    directory.mkdir()
    version = team.PROMPT_VERSION if agent == "team" else investigator.PROMPT_VERSION
    values = {"label": name, "agent": agent, "model": "qwen/qwen3-14b", "verifier_model": "", "rag": True,
              "prompt_version": version, "apply_fix": True} | params  # fmt: skip
    (directory / "params.json").write_text(json.dumps(values), encoding="utf-8")
    lines = [json.dumps(asdict(result(f"0{i}-s", ok))) for i, ok in enumerate(top1, 1)]
    (directory / "results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


@pytest.fixture
def results(tmp_path: Path) -> Path:
    backtest(tmp_path, "abl-single-r1", "llm", [True, False])
    backtest(tmp_path, "abl-single-r2", "llm", [False, False])
    backtest(tmp_path, "abl-team-r1", "team", [True, True], verifier_model="big")
    backtest(tmp_path, "abl-team-r2", "team", [True, False], verifier_model="big")
    backtest(tmp_path, "other", "llm", [True, True])
    (tmp_path / "old-without-params").mkdir()
    return tmp_path


def test_repeats_are_grouped_and_the_best_comes_first(results: Path) -> None:
    found = registry.configs(registry.backtests("abl-", results))
    assert [(c.params["agent"], len(c.runs)) for c in found] == [("team", 2), ("llm", 2)]
    assert found[0].scores()["top1"] == 1.5 and found[1].scores()["top1"] == 0.5


def test_fewer_sure_wrong_answers_break_a_tie(tmp_path: Path) -> None:
    backtest(tmp_path, "a", "llm", [True, False])
    sure = registry.configs(registry.backtests("", tmp_path))[0]
    (tmp_path / "a" / "results.jsonl").write_text(
        "\n".join(json.dumps(asdict(r)) for r in [result("01", True), result("02", False, "low")]), encoding="utf-8"
    )
    unsure = registry.configs(registry.backtests("", tmp_path))[0]
    assert unsure.rank() > sure.rank()


def test_import_once_then_register(results: Path, tmp_path: Path) -> None:
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    runs = registry.backtests("abl-", results)
    artifacts = tmp_path / "artifacts"
    assert registry.import_runs(runs, artifacts) == 4
    assert registry.import_runs(runs, artifacts) == 0  # the tag results_dir keeps it from logging a backtest twice
    assert artifacts.exists()
    versions = registry.register(registry.configs(runs)[0])
    assert set(versions) == {"ai-sre-investigator", "ai-sre-verifier"}
    prompt = mlflow.genai.load_prompt("prompts:/ai-sre-verifier@best")
    assert prompt.template == team.VERIFIER_PROMPT and prompt.tags["verifier_model"] == "big"


def test_a_changed_prompt_is_not_registered(tmp_path: Path) -> None:
    backtest(tmp_path, "old", "llm", [True], prompt_version="00000000")
    with pytest.raises(SystemExit, match="the prompt changed"):
        registry.register(registry.configs(registry.backtests("", tmp_path))[0])
