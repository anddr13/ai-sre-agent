"""The agent as a service: Alertmanager's webhook in, an investigation in the background, a Slack message out.

POST /alertmanager answers at once (Alertmanager must not wait minutes for an LLM); the investigation runs as
a task. The same firing group is investigated once per dedup_ttl_s, at most max_concurrent run at a time, and a
resolved notification is posted as a reply in the investigation's thread.
"""

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ai_sre_agent import investigator, tracking
from ai_sre_agent.config import Settings
from ai_sre_agent.investigator import Investigation
from ai_sre_agent.slack import Slack

log = logging.getLogger("ai_sre_agent")

Investigate = Callable[[dict[str, Any], Settings], Awaitable[Investigation]]


def _dedup_key(payload: dict[str, Any]) -> str:
    fingerprints = sorted(a.get("fingerprint", "") for a in payload.get("alerts", []) if a.get("status") == "firing")
    return f"{payload.get('groupKey', '')}|{','.join(fingerprints)}"


def _seconds_since(timestamp: str) -> float | None:
    try:
        started = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((datetime.now(UTC) - started).total_seconds(), 1)


def create_app(settings: Settings, investigate: Investigate = investigator.run, slack: Slack | None = None) -> FastAPI:
    app = FastAPI(title="ai-sre-agent")
    slack = slack or Slack(settings.slack_bot_token, settings.slack_channel)
    semaphore = asyncio.Semaphore(settings.max_concurrent)
    seen: dict[str, float] = {}  # dedup key -> monotonic time of the investigation
    threads: dict[str, str] = {}  # Alertmanager groupKey -> Slack thread ts
    tasks: set[asyncio.Task[None]] = set()
    app.state.tasks = tasks

    async def handle(payload: dict[str, Any]) -> None:
        group = payload.get("groupKey", "")
        async with semaphore:
            try:
                inv = await investigate(payload, settings)
            except Exception:
                log.exception("investigation crashed for %s", group)
                return
            delay = _seconds_since(inv.alert_started_at)
            log.info(
                "investigated %s: %s (confidence %s, %s tool calls, %ss, alert to answer %ss, audit %s)",
                inv.alertname,
                inv.summary,
                inv.confidence,
                inv.tool_calls,
                inv.duration_s,
                delay,
                inv.audit_path,
            )
            if slack.enabled:
                try:
                    threads[group] = await slack.post_investigation(inv)
                except Exception:
                    log.exception("posting to Slack failed")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/alertmanager")
    async def alertmanager(request: Request) -> JSONResponse:
        payload = await request.json()
        group = payload.get("groupKey", "")
        if payload.get("status") == "resolved":
            if group in threads and slack.enabled:
                names = sorted({a.get("labels", {}).get("alertname", "") for a in payload.get("alerts", [])})
                await slack.post(f":white_check_mark: Resolved: {', '.join(names)}", thread_ts=threads.pop(group))
            return JSONResponse({"status": "resolved"})

        key = _dedup_key(payload)
        now = time.monotonic()
        for old in [k for k, t in seen.items() if now - t > settings.dedup_ttl_s]:
            del seen[old]
        if key in seen:
            return JSONResponse({"status": "duplicate"})
        seen[key] = now

        task = asyncio.create_task(handle(payload))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return JSONResponse({"status": "investigating"}, status_code=202)

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    if not settings.llm_api_key:
        raise SystemExit("LLM_API_KEY is not set")
    tracking.setup(settings.mlflow_tracking_uri, settings.mlflow_experiment)
    uvicorn.run(
        create_app(settings),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
