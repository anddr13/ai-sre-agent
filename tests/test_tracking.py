"""MLflow tracking: off by default, and when on, a trace holds only what the model was allowed to see."""

import json
from collections.abc import Iterator
from pathlib import Path

import mlflow
import pytest
from test_investigator import PAYLOAD, FakeTools, ScriptedLlm, answer_reply, settings, tool_reply

from ai_sre_agent import tracking
from ai_sre_agent.audit import Audit
from ai_sre_agent.investigator import investigate


@pytest.fixture
def mlflow_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")  # the server uses Postgres; a test needs no database
    yield tmp_path / "mlruns"
    monkeypatch.setattr(tracking, "_enabled", False)


def test_off_without_a_tracking_uri(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("MLflow must not be called")

    monkeypatch.setattr(mlflow, "start_span", fail)
    monkeypatch.setattr(mlflow, "start_run", fail)
    assert not tracking.setup("", "x")
    with tracking.span("tool", "TOOL", {}) as span, tracking.run("x", {}):
        tracking.outputs(span, "result")
        tracking.log_metrics({"top1": 1.0})
    assert span is None


def test_unreachable_mlflow_leaves_tracking_off() -> None:
    assert not tracking.setup("http://127.0.0.1:9", "x")
    assert not tracking.enabled()


async def test_trace_has_the_redacted_tool_results(tmp_path: Path, mlflow_dir: Path) -> None:
    assert tracking.setup(mlflow_dir.as_uri(), "test")
    llm = ScriptedLlm([tool_reply('{"namespace": "voting"}'), answer_reply()])
    tools = FakeTools('{"podIP": "10.244.0.9", "env": "PGPASSWORD=hunter2"}')
    with tracking.span("investigate", "AGENT", {"alertname": "x"}):
        await investigate(PAYLOAD, settings(tmp_path), llm, tools, Audit(str(tmp_path), "x"))

    trace = mlflow.get_trace(mlflow.get_last_active_trace_id(), flush=True)
    spans = {s.name: s for s in trace.data.spans}
    assert set(spans) == {"investigate", "scripted", "k8s_events"}
    assert spans["scripted"].span_type == "CHAT_MODEL"
    tool = spans["k8s_events"]
    assert tool.span_type == "TOOL" and tool.parent_id == spans["investigate"].span_id
    text = json.dumps(tool.outputs)
    assert "<ip-1>" in text and "10.244.0.9" not in text and "hunter2" not in text


def test_backtest_run_has_params_and_metrics(mlflow_dir: Path) -> None:
    assert tracking.setup(mlflow_dir.as_uri(), "test")
    with tracking.run("label", {"model": "m"}):
        tracking.log_metrics({"top1": 6.0})
        run_id = mlflow.active_run().info.run_id
    run = mlflow.get_run(run_id)
    assert run.data.params == {"model": "m"} and run.data.metrics == {"top1": 6.0}
