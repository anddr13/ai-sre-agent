"""Investigators and a verifier: the same alert investigated by one agent per class of causes, in parallel, and
a verifier that keeps only the hypotheses their evidence supports.

Each investigator is the tool loop of the single agent with a narrower brief and a smaller budget. Each of its
hypotheses cites its own tool calls. A hypothesis that cites none is dropped in code; the verifier, an LLM without
tools, reads the cited results themselves and rejects the hypotheses they do not show, then ranks the rest. The
outcome is an ordinary Investigation, so Slack, the audit log and the backtest do not change.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from mcp import Client

from ai_sre_agent import tracking
from ai_sre_agent.audit import Audit
from ai_sre_agent.config import Settings
from ai_sre_agent.investigator import (
    STAND,
    Evidence,
    Investigation,
    Llm,
    Loop,
    McpTools,
    OpenAiLlm,
    Tools,
    _parse_answer,
    alert_name,
    alert_started_at,
    cited,
    describe_alerts,
    first_message,
    loop,
    retrieve,
    triage_of,
)
from ai_sre_agent.mcp_server.server import build_server
from ai_sre_agent.rag import Runbook
from ai_sre_agent.redact import Redactor

# The classes of causes from the plan; each investigator looks only at its own.
FOCUS = {
    "changes": (
        "deploys and configuration: what Argo CD synced and what changed in voting-gitops shortly before the alert "
        "(argocd_app_history, gitops_log with_diff): image tags, env variables, settings of Kafka, PostgreSQL, Redis"
    ),
    "resources": (
        "resources and limits: OOMKilled, restarts, CPU throttling, memory and CPU limits, pods that do not start "
        "or are not ready, autoscaling (KEDA), nodes"
    ),
    "dependencies": (
        "the dependencies of the app: Kafka brokers and partitions, PostgreSQL (primary, failover, connections, "
        "replication and WAL replay of the replicas), Redis, and the network between the app and them"
    ),
}

INVESTIGATOR_PROMPT = (
    """\
You are one of three SRE investigators working on the same alert in parallel, each on one class of causes.
Yours: {focus}.
The others cover the other classes: look outside yours only as far as you need to rule your class in or out.
You have read-only tools and cannot change anything.

"""
    + STAND
    + """

Find names with k8s_describe and k8s_events instead of guessing them. Every tool result is labelled [call N].
Be economical: 3-6 tool calls. If nothing in your class explains the alert, say so with an empty list: a
verifier reads your evidence, and a hypothesis it does not support only costs time.

When done, answer with only this JSON object, no other text:
{{"hypotheses": [{{"cause": "<the cause, with the specific object, revision or setting>",
                  "evidence": [{{"call": <N>, "finding": "<what this result shows>"}}],
                  "mitigation": "<what a human should do now>"}}],
 "impact": "<what your results show about users: errors, latency, since when, still going or resolved>"}}
At most two hypotheses, the most likely first. A hypothesis without evidence from your calls is dropped."""
)

VERIFIER_PROMPT = """\
You verify an incident investigation. Investigators proposed hypotheses for an alert; each cites tool results:
the tool, its arguments and the result (redacted, possibly cut). You have no tools. Judge every hypothesis only by
the results it cites:
- supported: the results show the claimed fact, and it explains the alert (the right object, the right time);
- rejected: the results do not show it or contradict it; it only restates the alert or a symptom ("the cluster
  has no primary", "the replica is lagging", "pods are not ready") instead of saying why; or it is generic
  ("misconfiguration", "dependency issues", "resource constraints") without the specific object.
Give a verdict for every hypothesis.
Then rank the supported hypotheses, the most likely root cause first; a cause comes before its own symptoms.
Hypotheses that name the same cause are one: rank only the best supported of them, so the ranking holds
different candidates.
Triage the alert: "wake" if users are affected or will be soon and someone must act now; "morning" if it needs a
fix but can wait for working hours; "noise" if it needs no action (a short spike that resolved by itself, no
errors, no user impact).

Answer with only this JSON object, no other text:
{"verdicts": [{"id": "H1", "supported": true, "reason": "<one sentence>"}],
 "ranking": ["<ids of the supported hypotheses, most likely first>"],
 "summary": "<one sentence: what is broken and why; or that the cause is not established>",
 "confidence": "high" | "medium" | "low",
 "mitigation": "<what a human should do now>",
 "triage": "wake" | "morning" | "noise"}
If no hypothesis is supported, "ranking" is empty and the confidence is "low"."""

PROMPT_VERSION = hashlib.sha256((INVESTIGATOR_PROMPT + "".join(FOCUS.values()) + VERIFIER_PROMPT).encode()).hexdigest()[
    :8
]
EVIDENCE_CHARS = 1_500  # of each cited result, for the verifier


@dataclass
class Hypothesis:
    id: str  # H1, H2, ... across all investigators
    investigator: str
    cause: str
    mitigation: str
    evidence: list[Evidence]  # call numbers renumbered across all investigators


@dataclass
class Report:
    investigator: str
    loop: Loop
    impact: str
    offset: int = 0  # its call N is call N + offset of the whole investigation


async def _investigator(
    name: str,
    payload: dict[str, Any],
    settings: Settings,
    llm: Llm,
    tools: Tools,
    specs: list[dict[str, Any]],
    audit: Audit,
    redact: Redactor,
    runbooks: list[Runbook] | None,
    limit: asyncio.Semaphore,
) -> Report:
    async with limit:
        with tracking.span(f"investigator {name}", "AGENT", {"focus": FOCUS[name]}) as span:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": INVESTIGATOR_PROMPT.format(focus=FOCUS[name])},
                {"role": "user", "content": first_message(payload, redact, runbooks)},
            ]
            out = await loop(
                messages,
                specs,
                settings,
                llm,
                tools,
                audit,
                redact,
                settings.investigator_max_steps,
                settings.investigator_max_tokens,
                agent=name,
            )
            tracking.outputs(span, out.answer)
    return Report(name, out, str((out.answer or {}).get("impact") or ""))


def hypotheses(reports: list[Report]) -> tuple[list[Hypothesis], list[str]]:
    """Every hypothesis of the investigators with its evidence; the ones that cite no real call are dropped."""
    kept, dropped = [], []
    for report in reports:
        for item in ((report.loop.answer or {}).get("hypotheses") or [])[:2]:
            if not isinstance(item, dict) or not item.get("cause"):
                continue
            cause = str(item["cause"])
            evidence = cited(item.get("evidence"), report.loop.calls, report.offset)
            if not evidence:
                dropped.append(f"{report.investigator}: {cause}")
                continue
            kept.append(
                Hypothesis(f"H{len(kept) + 1}", report.investigator, cause, str(item.get("mitigation") or ""), evidence)
            )
    return kept, dropped


def verifier_message(alert_text: str, reports: list[Report], candidates: list[Hypothesis]) -> str:
    results = {
        number + report.offset: result
        for report in reports
        for number, (_, _, result) in enumerate(report.loop.calls, start=1)
    }
    parts = [alert_text, "What the investigators saw of the impact:"]
    parts += [f"- {r.investigator}: {r.impact}" for r in reports if r.impact]
    parts.append("Hypotheses:")
    for h in candidates:
        lines = [f"{h.id} ({h.investigator}): {h.cause}"]
        for e in h.evidence:
            lines.append(f"  [call {e.call}] {e.tool} {json.dumps(e.arguments, ensure_ascii=False)}")
            lines.append(f"    claimed: {e.finding}")
            excerpt = results[e.call]
            if len(excerpt) > EVIDENCE_CHARS:
                excerpt = excerpt[:EVIDENCE_CHARS] + " ... [cut]"
            lines.append("    result: " + excerpt.replace("\n", "\n    "))
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


async def investigate(
    payload: dict[str, Any],
    settings: Settings,
    llm: Llm,
    tools: Tools,
    audit: Audit,
    runbooks: list[Runbook] | None = None,
    verifier: Llm | None = None,
) -> Investigation:
    """`verifier` defaults to `llm`."""
    verifier = verifier or llm
    started = time.monotonic()
    redact = Redactor()
    alertname = alert_name(payload)
    alert_text = redact(describe_alerts(payload))
    audit.write("alert", alertname=alertname, text=alert_text, group_key=payload.get("groupKey"))
    if runbooks:
        audit.write("runbooks", retrieved=[{"source": r.source, "score": r.score} for r in runbooks])
    specs = await tools.specs()
    audit.write(
        "start",
        model=llm.model,
        verifier_model=verifier.model,
        mode="team",
        investigators=list(FOCUS),
        prompt_version=PROMPT_VERSION,
    )

    limit = asyncio.Semaphore(settings.max_parallel_investigators)
    reports = list(
        await asyncio.gather(
            *(
                _investigator(name, payload, settings, llm, tools, specs, audit, redact, runbooks, limit)
                for name in FOCUS
            )
        )
    )
    offset = 0
    for report in reports:
        report.offset = offset
        offset += len(report.loop.calls)
    candidates, dropped = hypotheses(reports)
    audit.write(
        "hypotheses",
        kept=[{"id": h.id, "investigator": h.investigator, "cause": h.cause} for h in candidates],
        dropped_without_evidence=dropped,
    )

    verdict: dict[str, Any] = {}
    steps = sum(r.loop.steps for r in reports)
    tokens = sum(r.loop.tokens for r in reports)
    cost = sum(r.loop.cost for r in reports)
    error = "; ".join(f"{r.investigator}: {r.loop.error}" for r in reports if r.loop.error)
    if candidates:
        messages = [
            {"role": "system", "content": VERIFIER_PROMPT},
            {"role": "user", "content": verifier_message(alert_text, reports, candidates)},
        ]
        try:
            for _ in range(2):  # prose instead of JSON gets one more chance
                with tracking.span("verifier", "CHAT_MODEL", {"messages": messages}) as span:
                    reply = await asyncio.wait_for(
                        verifier.complete(messages, [], allow_tools=False), settings.llm_timeout_s
                    )
                    tracking.outputs(span, asdict(reply))
                steps, tokens, cost = steps + 1, tokens + reply.tokens, cost + reply.cost
                audit.write("llm", agent="verifier", content=reply.content, tokens=reply.tokens, cost=reply.cost)
                verdict = _parse_answer(reply.content) or {}
                if verdict:
                    break
                messages.append({"role": "assistant", "content": reply.content})
                messages.append({"role": "user", "content": "Answer with only the JSON object, please."})
        except Exception as exc:
            error = "; ".join(e for e in (error, f"verifier: {type(exc).__name__}: {exc}") if e)
            audit.write("error", agent="verifier", error=error)

    by_id = {h.id: h for h in candidates}
    verdicts = {str(v.get("id")): v for v in verdict.get("verdicts") or [] if isinstance(v, dict)}
    supported = {i for i, v in verdicts.items() if v.get("supported") is True}
    ranked = [
        by_id[i] for i in dict.fromkeys(str(i) for i in verdict.get("ranking") or []) if i in supported and i in by_id
    ]
    if not verdict and candidates:
        # No verdict (the verifier failed): the evidence-backed hypotheses in order, but nobody vouched for them.
        ranked, confidence = candidates, "low"
    else:
        confidence = str(verdict.get("confidence") or "low") if ranked else "low"
    rejected = [f"{h.id} {h.cause}: {verdicts.get(h.id, {}).get('reason', '')}" for h in candidates if h not in ranked]
    audit.write("verdict", ranking=[h.id for h in ranked], rejected=rejected)

    top = ranked[0] if ranked else None
    investigation = Investigation(
        investigation_id=audit.investigation_id,
        alertname=alertname,
        summary=str(verdict.get("summary") or ("No cause supported by evidence" if not top else top.cause)),
        root_cause=top.cause if top else "",
        confidence=confidence,
        mitigation=str(verdict.get("mitigation") or (top.mitigation if top else "")),
        triage=triage_of(verdict.get("triage")),
        alternatives=[h.cause for h in ranked[1:3]],
        evidence=top.evidence if top else [],
        stopped_by="error" if error and not top else "answer",
        model=llm.model if verifier.model == llm.model else f"{llm.model} + verifier {verifier.model}",
        steps=steps,
        tool_calls=offset,
        tokens=tokens,
        cost_usd=round(cost, 6),
        duration_s=round(time.monotonic() - started, 1),
        audit_path=str(audit.path),
        error=error,
        alert_started_at=alert_started_at(payload),
        prompt_version=PROMPT_VERSION,
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    audit.write("result", **asdict(investigation))
    return investigation


async def run(payload: dict[str, Any], settings: Settings) -> Investigation:
    """A team investigation with the real LLM and the real MCP server (one client session, shared)."""
    alertname = alert_name(payload)
    audit = Audit(settings.audit_dir, alertname)
    with tracking.span("investigate", "AGENT", {"alertname": alertname, "mode": "team"}) as span:
        runbooks = await retrieve(payload, settings, audit)
        async with Client(build_server(settings)) as client:
            llm, verifier = OpenAiLlm(settings), OpenAiLlm(settings, settings.verifier_model)
            result = await investigate(payload, settings, llm, McpTools(client), audit, runbooks, verifier)
        tracking.outputs(span, {"root_cause": result.root_cause, "triage": result.triage, "error": result.error})
    return result
