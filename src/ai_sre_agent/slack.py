"""The investigation as a Slack message: hypothesis, evidence (the exact tool call and what it returned),
suggested mitigation. Posted with chat.postMessage; a resolved alert is answered in the same thread."""

import json
from typing import Any

import httpx

from ai_sre_agent.investigator import Investigation

API = "https://slack.com/api/chat.postMessage"
CONFIDENCE = {"high": ":large_green_circle:", "medium": ":large_yellow_circle:", "low": ":red_circle:"}
TRIAGE = {"wake": "wake someone now", "morning": "can wait until morning", "noise": "noise, no action"}


def _call(tool: str, arguments: dict[str, Any]) -> str:
    args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in arguments.items())
    return f"{tool}({args})"


def _code(text: str, limit: int) -> str:
    text = text.replace("```", "'''")
    return text if len(text) <= limit else text[:limit] + " …"


def blocks(inv: Investigation) -> list[dict[str, Any]]:
    title = f"{':zzz: ' if inv.noise else ':rotating_light: '}{inv.alertname}"
    header = [
        {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{_code(inv.summary, 2500)}*"}},
    ]
    if inv.error and not inv.root_cause:
        body = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Investigation failed: `{_code(inv.error, 500)}`"}}
        ]
    else:
        body = [
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Root cause*\n{_code(inv.root_cause, 1900)}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence*\n{CONFIDENCE.get(inv.confidence, '')} {inv.confidence}"
                        f"\n*Triage*: {TRIAGE.get(inv.triage, inv.triage)}",
                    },
                ],
            }
        ]
        for ev in inv.evidence[:6]:
            body.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Evidence {ev.call}*: {_code(ev.finding, 600)}\n"
                        f"`{_code(_call(ev.tool, ev.arguments), 300)}`\n```{_code(ev.result_excerpt, 500)}```",
                    },
                }
            )
        if inv.alternatives:
            others = "\n".join(f"• {_code(a, 400)}" for a in inv.alternatives)
            body.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Other candidates*\n{others}"}})
        if not inv.evidence:
            body.append({"type": "section", "text": {"type": "mrkdwn", "text": "_No evidence cited._"}})
        body.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Suggested mitigation*\n{_code(inv.mitigation, 2500)}"},
            }
        )
    footer = {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"{inv.model} · {inv.steps} LLM turns, {inv.tool_calls} tool calls · {inv.tokens} tokens"
                f" · ${inv.cost_usd:.4f} · {inv.duration_s:.0f}s · stopped by {inv.stopped_by}"
                f" · investigation `{inv.investigation_id}` · read-only, nothing was changed",
            }
        ],
    }
    return [*header, {"type": "divider"}, *body, footer]


class Slack:
    def __init__(self, token: str, channel: str):
        self._token = token
        self._channel = channel

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._channel)

    async def post(self, text: str, blocks: list[dict[str, Any]] | None = None, thread_ts: str | None = None) -> str:
        """Posts a message and returns its ts (the thread id for replies)."""
        payload: dict[str, Any] = {"channel": self._channel, "text": text, "unfurl_links": False}
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(API, json=payload, headers={"Authorization": f"Bearer {self._token}"})
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Slack chat.postMessage failed: {body.get('error')}")
        return str(body["ts"])

    async def post_investigation(self, inv: Investigation) -> str:
        return await self.post(f"{inv.alertname}: {inv.summary}", blocks(inv))
