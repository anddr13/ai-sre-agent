"""MLflow: a backtest is an MLflow run with its scores, an investigation is a trace.

The trace of an investigation has the LLM calls and the tool calls as spans with the redacted
results, the same text the model saw. Everything here is a no-op until `setup()` gets a tracking URI
(MLFLOW_TRACKING_URI); the agent in the cluster then traces the real alerts too.
"""

import contextlib
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import mlflow

log = logging.getLogger(__name__)
_enabled = False


def setup(tracking_uri: str, experiment: str) -> bool:
    """Turn tracking on; an unreachable MLflow is logged and leaves it off rather than stopping the agent."""
    global _enabled
    if not tracking_uri:
        return False
    try:
        if tracking_uri.startswith("http"):  # MLflow's own client retries for minutes before it gives up
            httpx.get(f"{tracking_uri.rstrip('/')}/health", timeout=5).raise_for_status()
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)
    except Exception as exc:
        log.warning("MLflow at %s is not available, tracking is off: %s", tracking_uri, exc)
        return False
    _enabled = True
    return True


def enabled() -> bool:
    return _enabled


@contextlib.contextmanager
def span(name: str, span_type: str, inputs: dict[str, Any]) -> Iterator[Any]:
    """A span of the current trace (a new trace if there is none); None when tracking is off."""
    if not _enabled:
        yield None
        return
    with mlflow.start_span(name=name, span_type=span_type) as current:
        current.set_inputs(inputs)
        yield current


def outputs(current: Any, value: Any) -> None:
    if current is not None:
        current.set_outputs(value)


@contextlib.contextmanager
def run(name: str, params: dict[str, Any]) -> Iterator[None]:
    """An MLflow run around a backtest; the traces made inside it are linked to it."""
    if not _enabled:
        yield
        return
    with mlflow.start_run(run_name=name):
        mlflow.log_params(params)
        try:
            yield
        finally:
            mlflow.flush_trace_async_logging()  # traces are exported in the background


def log_metrics(metrics: dict[str, float], step: int | None = None) -> None:
    if _enabled:
        mlflow.log_metrics(metrics, step=step)


def log_artifact(path: Path) -> None:
    if _enabled and path.exists():
        mlflow.log_artifact(str(path))
