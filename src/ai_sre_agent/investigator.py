"""One investigation: an alert goes in, a root-cause hypothesis with evidence and a suggested mitigation comes out.

A single agent loop with tool calling. The tools are the read-only MCP server, reached through an MCP client
session; the LLM is any OpenAI-compatible endpoint. Every tool result is redacted before the model sees it,
every step is written to the audit log, and the loop is bounded by steps, tokens and timeouts.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from mcp import Client
from openai import AsyncOpenAI

from ai_sre_agent import rag, tracking
from ai_sre_agent.audit import Audit
from ai_sre_agent.config import Settings
from ai_sre_agent.mcp_server.server import build_server
from ai_sre_agent.redact import Redactor

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an SRE on call. An alert fired on a Kubernetes stand and you investigate it with read-only tools.
You cannot change anything; a human decides what to do with your answer.

The stand: the voting app in namespace voting (vote-api and result-api behind Traefik, worker consuming Kafka,
scaled by KEDA on consumer lag), Kafka by Strimzi (3 brokers, voting-dual-role-0..2), PostgreSQL by CloudNativePG
(cluster voting-pg, services voting-pg-rw / voting-pg-ro), Redis. Argo CD deploys everything from the
voting-gitops repository (branch lab): Applications voting (the app), data (Kafka, PostgreSQL, Redis), alerts.
Monitoring (Prometheus, Loki) is in namespace monitoring.
voting-gitops layout: charts/voting (the app; image.tag in charts/voting/values.yaml), charts/data (Kafka,
PostgreSQL, Redis; their settings in charts/data/values.yaml), charts/alerts, envs/local.yaml (this stand's
overrides), apps/ (the Argo CD Applications). A commit "voting: release <sha>" is a new image tag.

How to investigate:
1. Read the alert: what is affected, since when.
2. Check what changed shortly before: argocd_app_history of the related Application and gitops_log with_diff.
   Most incidents follow a change, but not all: hardware and load fail too.
3. Look at the affected objects: k8s_describe, k8s_events. Find names there instead of guessing them.
4. Confirm with metrics (prometheus_query) and logs (loki_query).
5. Stop as soon as the evidence supports one cause. Be economical: usually 4-8 tool calls are enough.

Every tool result is labelled [call N]. Cite those numbers as evidence. Separate the cause from its symptoms.
Triage the alert: "wake" if users are affected or will be soon and someone must act now; "morning" if it needs a
fix but can wait for working hours; "noise" if it needs no action (a short spike that resolved by itself, no
errors, no user impact).
The mitigation is advice for a human (for example "git revert <sha> on branch lab of voting-gitops"),
never something you did.

When done, answer with only this JSON object, no other text:
{"summary": "<one sentence: what is broken and why>",
 "root_cause": "<the most likely cause, with the specific object, revision or setting>",
 "alternatives": ["<the second most likely cause>", "<the third>"],
 "confidence": "high" | "medium" | "low",
 "evidence": [{"call": <N>, "finding": "<what this result shows>"}],
 "mitigation": "<what a human should do now>",
 "triage": "wake" | "morning" | "noise"}
"alternatives" may be empty when the evidence leaves no other candidate."""

# Changes with every edit of the prompt, so backtest results can be grouped by prompt version.
PROMPT_VERSION = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8]
TRIAGE = ("wake", "morning", "noise")

FINAL_NUDGE = (
    "The investigation budget is used up. Give your final answer now, as the JSON object described in the "
    "instructions, based on the evidence you already have. Lower the confidence if the evidence is thin."
)


# --- the two seams: tools and LLM --------------------------------------------------------------------


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON text, as the model produced it


@dataclass
class Reply:
    content: str
    tool_calls: list[ToolCall]
    tokens: int
    cost: float


class Tools(Protocol):
    async def specs(self) -> list[dict[str, Any]]: ...
    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]: ...


class Llm(Protocol):
    model: str

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], allow_tools: bool
    ) -> Reply: ...


class McpTools:
    """The read-only MCP server, through a real MCP client session (in-process)."""

    def __init__(self, client: Client):
        self._client = client

    async def specs(self) -> list[dict[str, Any]]:
        tools = (await self._client.list_tools()).tools
        return [
            {
                "type": "function",
                "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema},
            }
            for t in tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        result = await self._client.call_tool(name, arguments)
        text = "\n".join(getattr(part, "text", "") for part in result.content)
        return bool(result.is_error), text


class OpenAiLlm:
    def __init__(self, settings: Settings):
        self.model = settings.llm_model
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key, timeout=settings.llm_timeout_s, max_retries=2
        )

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], allow_tools: bool) -> Reply:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            tool_choice="auto" if allow_tools else "none",
            temperature=0,
            max_tokens=4000,
        )
        message = response.choices[0].message
        usage = response.usage
        cost = (usage.model_extra or {}).get("cost") if usage else None  # OpenRouter reports the price
        return Reply(
            content=message.content or "",
            tool_calls=[
                ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
                for c in message.tool_calls or []
                if c.type == "function"
            ],
            tokens=usage.total_tokens if usage else 0,
            cost=float(cost or 0.0),
        )


# --- the result -----------------------------------------------------------------------------------------


@dataclass
class Evidence:
    call: int
    tool: str
    arguments: dict[str, Any]
    finding: str
    result_excerpt: str


@dataclass
class Investigation:
    investigation_id: str
    alertname: str
    summary: str
    root_cause: str
    confidence: str
    mitigation: str
    triage: str  # wake | morning | noise
    alternatives: list[str]
    evidence: list[Evidence]
    stopped_by: str  # answer | max_steps | max_tokens | error
    model: str
    steps: int
    tool_calls: int
    tokens: int
    cost_usd: float
    duration_s: float
    audit_path: str
    error: str = ""
    alert_started_at: str = ""
    prompt_version: str = PROMPT_VERSION
    finished_at: str = ""

    @property
    def noise(self) -> bool:
        return self.triage == "noise"

    @property
    def hypotheses(self) -> list[str]:
        """The ranked candidates: the root cause first, then the alternatives."""
        return [h for h in (self.root_cause, *self.alternatives) if h][:3]


# --- the loop -----------------------------------------------------------------------------------------


def describe_alerts(payload: dict[str, Any]) -> str:
    """The firing alerts of an Alertmanager webhook payload, as the text the model starts from."""
    lines = []
    for alert in payload.get("alerts", []):
        if alert.get("status") != "firing":
            continue
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        lines.append(f"Alert {labels.get('alertname')} firing since {alert.get('startsAt')}")
        lines.append("  labels: " + ", ".join(f"{k}={v}" for k, v in sorted(labels.items()) if k != "alertname"))
        for key in ("summary", "description", "runbook_url"):
            if annotations.get(key):
                lines.append(f"  {key}: {annotations[key]}")
    return "\n".join(lines) or "No firing alerts in the payload."


def _parse_answer(text: str) -> dict[str, Any] | None:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        answer = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return answer if isinstance(answer, dict) else None


async def investigate(
    payload: dict[str, Any],
    settings: Settings,
    llm: Llm,
    tools: Tools,
    audit: Audit,
    runbooks: list[rag.Runbook] | None = None,
) -> Investigation:
    started = time.monotonic()
    redact = Redactor()
    firing = [a for a in payload.get("alerts", []) if a.get("status") == "firing"]
    alertname = (payload.get("commonLabels") or {}).get("alertname") or (
        firing[0]["labels"].get("alertname", "unknown") if firing else "unknown"
    )
    alert_text = redact(describe_alerts(payload))
    audit.write("alert", alertname=alertname, text=alert_text, group_key=payload.get("groupKey"))

    if runbooks:
        audit.write("runbooks", retrieved=[{"source": r.source, "score": r.score} for r in runbooks])
    first = [alert_text, rag.context(runbooks or []), "Investigate."]

    specs = await tools.specs()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(part for part in first if part)},
    ]
    audit.write("start", model=llm.model, system_prompt=SYSTEM_PROMPT, tools=[s["function"]["name"] for s in specs])

    calls: list[tuple[str, dict[str, Any], str]] = []  # (tool, arguments, redacted result), index = call - 1
    tokens, cost, steps, stopped_by, answer, error = 0, 0.0, 0, "max_steps", None, ""

    try:
        while steps < settings.max_steps and answer is None:
            # The last turn, or out of tokens: no more tools, the model has to answer with what it has.
            out_of_budget = tokens >= settings.max_tokens
            forced = out_of_budget or steps == settings.max_steps - 1
            if forced:
                stopped_by = "max_tokens" if out_of_budget else "max_steps"
                messages.append({"role": "user", "content": FINAL_NUDGE})
            with tracking.span(llm.model, "CHAT_MODEL", {"messages": messages, "allow_tools": not forced}) as span:
                reply = await asyncio.wait_for(
                    llm.complete(messages, specs, allow_tools=not forced), settings.llm_timeout_s
                )
                tracking.outputs(span, asdict(reply))
            steps += 1
            tokens += reply.tokens
            cost += reply.cost
            audit.write(
                "llm",
                step=steps,
                content=reply.content,
                tool_calls=[{"name": c.name, "arguments": c.arguments} for c in reply.tool_calls],
                tokens=reply.tokens,
                cost=reply.cost,
            )

            if not reply.tool_calls:
                answer = _parse_answer(reply.content)
                if answer is None:  # prose instead of JSON: ask once more for the format
                    messages.append({"role": "assistant", "content": reply.content})
                    messages.append({"role": "user", "content": "Answer with only the JSON object, please."})
                    continue
                if not forced:
                    stopped_by = "answer"
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": reply.content,
                    "tool_calls": [
                        {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}}
                        for c in reply.tool_calls
                    ],
                }
            )
            for call in reply.tool_calls:
                number = len(calls) + 1
                with tracking.span(call.name, "TOOL", {"call": number, "arguments": call.arguments}) as span:
                    try:
                        arguments = json.loads(call.arguments or "{}")
                        if not isinstance(arguments, dict):
                            raise ValueError("arguments must be a JSON object")
                        is_error, text = await asyncio.wait_for(
                            tools.call(call.name, arguments), settings.tool_timeout_s + 5
                        )
                    except ValueError as exc:  # includes malformed JSON
                        arguments, is_error, text = {}, True, f"invalid arguments: {exc}"
                    except TimeoutError:
                        arguments, is_error, text = arguments, True, "the tool did not answer in time"
                    result = redact(text)
                    if len(result) > settings.max_tool_result_chars:
                        result = result[: settings.max_tool_result_chars] + "\n... [truncated]"
                    tracking.outputs(span, {"error": is_error, "result": result})
                calls.append((call.name, arguments, result))
                audit.write("tool", call=number, name=call.name, arguments=arguments, error=is_error, result=result)
                prefix = f"[call {number}] {'ERROR ' if is_error else ''}"
                messages.append({"role": "tool", "tool_call_id": call.id, "content": prefix + result})
    except Exception as exc:  # the LLM endpoint failing must still produce a message and an audit record
        stopped_by, error = "error", f"{type(exc).__name__}: {exc}"
        audit.write("error", error=error)

    answer = answer or {}
    triage = str(answer.get("triage") or "").lower()
    if triage not in TRIAGE:  # unknown or missing: never silence an alert by accident
        triage = "wake"
    evidence = []
    for item in answer.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("call", 0))
        except (TypeError, ValueError):
            continue
        if 1 <= number <= len(calls):  # only evidence that points at a real tool result
            tool, arguments, result = calls[number - 1]
            evidence.append(Evidence(number, tool, arguments, str(item.get("finding", "")), result[:600]))

    investigation = Investigation(
        investigation_id=audit.investigation_id,
        alertname=alertname,
        summary=str(answer.get("summary") or ("Investigation failed" if error else "No conclusion")),
        root_cause=str(answer.get("root_cause") or ""),
        confidence=str(answer.get("confidence") or "low"),
        mitigation=str(answer.get("mitigation") or ""),
        triage=triage,
        alternatives=[str(a) for a in (answer.get("alternatives") or []) if a][:2],
        evidence=evidence,
        stopped_by=stopped_by,
        model=llm.model,
        steps=steps,
        tool_calls=len(calls),
        tokens=tokens,
        cost_usd=round(cost, 6),
        duration_s=round(time.monotonic() - started, 1),
        audit_path=str(audit.path),
        error=error,
        alert_started_at=min((a.get("startsAt", "") for a in firing), default=""),
        finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    audit.write("result", **asdict(investigation))
    return investigation


async def retrieve(payload: dict[str, Any], settings: Settings, audit: Audit) -> list[rag.Runbook]:
    """The runbooks closest to the alert; none when RAG is off or its database is down (the agent still works)."""
    if not settings.rag_database_url:
        return []
    query = Redactor()(describe_alerts(payload))
    with tracking.span("retrieve", "RETRIEVER", {"query": query}) as span:
        try:
            embedder = rag.embedder(settings.embedding_cache_dir)
            runbooks = await rag.search(settings.rag_database_url, embedder, query, settings.rag_top_k)
        except Exception as exc:
            log.warning("runbook retrieval failed: %s", exc)
            audit.write("runbooks", error=f"{type(exc).__name__}: {exc}")
            return []
        tracking.outputs(span, [{"source": r.source, "score": r.score} for r in runbooks])
    return runbooks


async def run(payload: dict[str, Any], settings: Settings) -> Investigation:
    """An investigation with the real LLM and the real MCP server."""
    firing = [a for a in payload.get("alerts", []) if a.get("status") == "firing"]
    alertname = firing[0]["labels"].get("alertname", "alert") if firing else "alert"
    audit = Audit(settings.audit_dir, alertname)
    with tracking.span("investigate", "AGENT", {"alertname": alertname}) as span:
        runbooks = await retrieve(payload, settings, audit)
        async with Client(build_server(settings)) as client:
            result = await investigate(payload, settings, OpenAiLlm(settings), McpTools(client), audit, runbooks)
        tracking.outputs(span, {"root_cause": result.root_cause, "triage": result.triage, "error": result.error})
    return result
