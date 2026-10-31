"""Run one investigation by hand, without Alertmanager's webhook: the alert is read from Alertmanager's API.

    uv run ai-sre-investigate VotingPodNotStarting            # prints the result as JSON
    uv run ai-sre-investigate VotingPodNotStarting --slack    # and posts it

The backtest runner will use the same path.
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from typing import Any

import httpx

from ai_sre_agent import investigator
from ai_sre_agent.config import Settings
from ai_sre_agent.slack import Slack

ALERTMANAGER_URL = os.environ.get(
    "ALERTMANAGER_URL", "http://localhost:8090/api/datasources/proxy/uid/alertmanager"
).rstrip("/")


async def webhook_payload(alertname: str, settings: Settings) -> dict[str, Any]:
    """The active alerts named alertname, shaped like Alertmanager's webhook body."""
    headers = {"Host": settings.http_host_header} if settings.http_host_header else {}
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        response = await client.get(
            f"{ALERTMANAGER_URL}/api/v2/alerts", params={"active": "true", "filter": f'alertname="{alertname}"'}
        )
    response.raise_for_status()
    alerts = [
        {
            "status": "firing",
            "labels": a["labels"],
            "annotations": a.get("annotations", {}),
            "startsAt": a["startsAt"],
            "fingerprint": a["fingerprint"],
        }
        for a in response.json()
    ]
    if not alerts:
        raise SystemExit(f"no active alert named {alertname}")
    return {
        "status": "firing",
        "groupKey": f"manual/{alertname}",
        "commonLabels": {"alertname": alertname},
        "alerts": alerts,
    }


async def main_async(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    payload = await webhook_payload(args.alertname, settings)
    inv = await investigator.run(payload, settings)
    print(json.dumps(asdict(inv), indent=2, ensure_ascii=False))
    if args.slack:
        await Slack(settings.slack_bot_token, settings.slack_channel).post_investigation(inv)
        print("posted to Slack", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("alertname")
    parser.add_argument("--slack", action="store_true", help="post the result to Slack")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
