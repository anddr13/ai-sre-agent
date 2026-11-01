"""The baseline without an LLM: one fixed playbook per alert, using the same read-only MCP tools.

It encodes what an on-call engineer with the runbooks would check first. The backtest runs it on the same
scenarios as the agent (`ai-sre-backtest --agent rules`), which shows where the LLM actually adds something.
"""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp import Client

from ai_sre_agent import tracking
from ai_sre_agent.audit import Audit
from ai_sre_agent.config import Settings
from ai_sre_agent.investigator import Evidence, Investigation, McpTools, Tools
from ai_sre_agent.mcp_server.server import build_server
from ai_sre_agent.redact import Redactor

MODEL = "rules"
PROMPT_VERSION = "rules-v1"


@dataclass
class Finding:
    root_cause: str
    triage: str
    mitigation: str
    evidence: list[Evidence]


class Session:
    """Tool calls of one rule-based investigation, recorded like the agent's."""

    def __init__(self, tools: Tools, audit: Audit):
        self._tools = tools
        self._audit = audit
        self._redact = Redactor()
        self.calls = 0

    async def call(self, tool: str, finding: str, **arguments: Any) -> tuple[dict[str, Any], Evidence]:
        self.calls += 1
        with tracking.span(tool, "TOOL", {"call": self.calls, "arguments": arguments}) as span:
            is_error, text = await self._tools.call(tool, arguments)
            result = self._redact(text)
            tracking.outputs(span, {"error": is_error, "result": result})
        self._audit.write("tool", call=self.calls, name=tool, arguments=arguments, error=is_error, result=result)
        try:
            data = {} if is_error else json.loads(text)  # the rules read the raw result; only what is kept is redacted
        except ValueError:
            data = {}
        return data, Evidence(self.calls, tool, arguments, finding, result[:600])


async def _latest_change(s: Session, path: str | None = None) -> tuple[str, Evidence]:
    """The newest commit on the GitOps branch: the rule's only idea of 'what changed'."""
    args: dict[str, Any] = {"since": "2h", "max_count": 1}
    if path:
        args["path"] = path
    data, ev = await s.call("gitops_log", "the newest change of the desired state", **args)
    commits = data.get("commits_newest_first") or []
    if not commits:
        return "no change in the last 2h", ev
    c = commits[0]
    return f"revision {c['sha'][:7]} ({c['subject']})", ev


async def _pod_not_starting(s: Session, labels: dict[str, str]) -> Finding:
    data, ev = await s.call(
        "k8s_describe", "the waiting container", kind="pod", namespace=labels["namespace"], name=labels["pod"]
    )
    states = [c.get("state") or {} for c in data.get("containers", [])]
    waiting = next((st["waiting"] for st in states if "waiting" in st), {})
    image = next((c.get("image") for c in data.get("containers", []) if c.get("image")), "?")
    change, ev2 = await _latest_change(s, "charts/voting")
    return Finding(
        f"{labels['pod']} cannot start: {waiting.get('reason', 'waiting')} for image {image}; latest change {change}",
        "wake",
        f"Roll back the latest change ({change}) in voting-gitops",
        [ev, ev2],
    )


async def _latest_change_caused_it(s: Session, symptom: str, path: str | None = None) -> Finding:
    change, ev = await _latest_change(s, path)
    return Finding(f"{symptom}, caused by the latest change: {change}", "wake", f"Revert {change}", [ev])


async def _kafka(s: Session, labels: dict[str, str]) -> Finding:
    _, ev = await s.call(
        "prometheus_query",
        "under-replicated partitions",
        query='sum by (topic) (kafka_topic_partition_under_replicated_partition{namespace="voting"})',
    )
    return Finding(
        f"A Kafka broker is down or out of the ISR: topic {labels.get('topic', '?')} has under-replicated partitions",
        "wake",
        "Find the broker that is not in sync and restart it",
        [ev],
    )


async def _failover(s: Session, labels: dict[str, str]) -> Finding:
    _, ev = await s.call(
        "prometheus_query", "which instance is primary", query='cnpg_pg_replication_in_recovery{namespace="voting"}'
    )
    return Finding(
        "PostgreSQL failover: the primary of voting-pg was lost and a replica promoted",
        "wake",
        "Check that the new primary accepts writes",
        [ev],
    )


async def _replica_lag(s: Session, labels: dict[str, str]) -> Finding:
    data, ev = await s.call(
        "prometheus_query",
        "replication lag per instance",
        query='max by (pod) (cnpg_pg_replication_lag{namespace="voting"})',
    )
    series = data.get("series") or []
    worst = max(series, key=lambda x: float(x["value"][1]), default=None)
    pod = worst["labels"].get("pod", "?") if worst else labels.get("pod", "?")
    return Finding(
        f"Replica {pod} has replication lag; reads through voting-pg-ro are stale",
        "morning",
        f"Look at what slows replay on {pod}",
        [ev],
    )


async def _oom(s: Session, labels: dict[str, str]) -> Finding:
    change, ev = await _latest_change(s)
    return Finding(
        f"{labels.get('container', '?')} was OOMKilled: its memory limit is too low; latest change {change}",
        "wake",
        f"Raise the memory limit of {labels.get('container', '?')} (or revert {change})",
        [ev],
    )


def _playbooks() -> dict[str, Callable[[Session, dict[str, str]], Awaitable[Finding]]]:
    return {
        "VotingPodNotStarting": _pod_not_starting,
        "VotingHttp5xxRate": lambda s, _: _latest_change_caused_it(s, "vote-api/result-api answer with 5xx"),
        "KafkaUnderReplicatedPartitions": _kafka,
        "PostgresPrimaryFailover": _failover,
        "PostgresConnectionsHigh": lambda s, _: _latest_change_caused_it(s, "PostgreSQL is out of connections"),
        "PostgresReplicationLag": _replica_lag,
        "ContainerOOMKilled": _oom,
    }


async def investigate(payload: dict[str, Any], tools: Tools, audit: Audit) -> Investigation:
    started = time.monotonic()
    firing = [a for a in payload.get("alerts", []) if a.get("status") == "firing"]
    labels = firing[0]["labels"] if firing else {}
    alertname = labels.get("alertname", "unknown")
    audit.write("alert", alertname=alertname, labels=labels)
    session = Session(tools, audit)
    playbook = _playbooks().get(alertname)
    error = ""
    if playbook is None:
        # No rule: the alert's severity decides, which is all a rule can know about a latency blip.
        triage = "wake" if labels.get("severity") == "critical" else "morning"
        finding = Finding(f"{alertname} fired; no playbook for it", triage, "Look at the alert", [])
    else:
        try:
            finding = await playbook(session, labels)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            finding = Finding("", "wake", "", [])
    result = Investigation(
        investigation_id=audit.investigation_id,
        alertname=alertname,
        summary=finding.root_cause.split(":")[0] if finding.root_cause else "No conclusion",
        root_cause=finding.root_cause,
        confidence="medium",
        mitigation=finding.mitigation,
        triage=finding.triage,
        alternatives=[],
        evidence=finding.evidence,
        stopped_by="error" if error else "answer",
        model=MODEL,
        steps=0,
        tool_calls=session.calls,
        tokens=0,
        cost_usd=0.0,
        duration_s=round(time.monotonic() - started, 1),
        audit_path=str(audit.path),
        error=error,
        alert_started_at=min((a.get("startsAt", "") for a in firing), default=""),
        prompt_version=PROMPT_VERSION,
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    audit.write("result", root_cause=result.root_cause, triage=result.triage, error=error)
    return result


async def run(payload: dict[str, Any], settings: Settings) -> Investigation:
    firing = [a for a in payload.get("alerts", []) if a.get("status") == "firing"]
    alertname = firing[0]["labels"].get("alertname", "alert") if firing else "alert"
    audit = Audit(settings.audit_dir, f"rules-{alertname}")
    with tracking.span("investigate", "AGENT", {"alertname": alertname, "agent": MODEL}) as span:
        async with Client(build_server(settings)) as client:
            result = await investigate(payload, McpTools(client), audit)
        tracking.outputs(span, {"root_cause": result.root_cause, "triage": result.triage, "error": result.error})
    return result
