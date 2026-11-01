"""The backtest: break the stand in known ways, let the agent investigate, score its answer against the cause
that was written down before it started, put the stand back.

    uv run ai-sre-backtest                          # all eight scenarios, once
    uv run ai-sre-backtest --scenarios 01,08 --runs 3 --label stability
    uv run ai-sre-backtest --agent rules --label rules     # the baseline without an LLM

For every scenario: wait until the stand is quiet, scenarios/NN/break.sh (which writes the expected answer and
waits for the alert), fetch the alert from Alertmanager, investigate, score, scenarios/NN/restore.sh (always).
While it runs, a silence keeps Alertmanager from also sending the alerts to the agent in the cluster.
Results: backtest/results/<time>-<label>/results.jsonl and summary.md.
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import yaml

from ai_sre_agent import investigator, rules
from ai_sre_agent.cli import ALERTMANAGER_URL, webhook_payload
from ai_sre_agent.config import REPO_ROOT, Settings
from ai_sre_agent.investigator import Investigation

SCENARIOS_DIR = REPO_ROOT / "scenarios"
RESULTS_DIR = REPO_ROOT / "backtest" / "results"
ALL = [
    "01-bad-deploy", "02-config-regression", "03-kafka-broker-down", "04-postgres-failover",
    "05-postgres-connections", "06-replica-lag", "07-redis-oom", "08-noise",
]  # fmt: skip
SCRIPT_TIMEOUT_S = 20 * 60


@dataclass
class Result:
    scenario: str
    run: int
    alert: str
    expected_triage: str
    correct_rank: int | None  # 1-3: which hypothesis matched the known cause; None: none did
    top1: bool
    top3: bool
    triage: str
    triage_ok: bool
    confidence: str
    hypotheses: list[str]
    alert_to_answer_s: float | None
    investigation_s: float
    tokens: int
    cost_usd: float
    steps: int
    tool_calls: int
    stopped_by: str
    model: str
    prompt_version: str
    audit_path: str
    error: str = ""


def score(inv: Investigation, expected: dict[str, Any]) -> tuple[int | None, bool]:
    """(rank of the first hypothesis that matches every pattern, whether the triage label is acceptable)."""
    triage_ok = re.fullmatch(str(expected.get("triage", "wake")), inv.triage) is not None
    if expected.get("triage") == "noise":  # the noise scenario is about the label, not an explanation
        return (1 if inv.triage == "noise" else None), triage_ok
    patterns = [p for p in expected.get("match") or [] if p]
    for rank, hypothesis in enumerate(inv.hypotheses, start=1):
        text = f"{hypothesis} {inv.summary}" if rank == 1 else hypothesis
        if patterns and all(re.search(p, text, re.IGNORECASE) for p in patterns):
            return rank, triage_ok
    return None, triage_ok


def _bash() -> str:
    # Never WSL's bash (C:\Windows\System32\bash.exe): the scenarios need Git Bash on Windows, or any bash elsewhere.
    candidate = os.environ.get("BACKTEST_BASH") or r"C:\Program Files\Git\bin\bash.exe"
    return candidate if Path(candidate).exists() else (shutil.which("bash") or "bash")


def run_script(path: Path, log: Path) -> None:
    with log.open("a", encoding="utf-8") as out:
        out.write(f"\n$ {path.relative_to(REPO_ROOT)}\n")
        out.flush()
        completed = subprocess.run(
            [_bash(), str(path)], stdout=out, stderr=subprocess.STDOUT, timeout=SCRIPT_TIMEOUT_S, check=False
        )
    if completed.returncode != 0:
        raise RuntimeError(f"{path.parent.name}/{path.name} failed with exit code {completed.returncode} (see {log})")


class Stand:
    """Prometheus and Alertmanager of the stand, through Grafana's datasource proxy."""

    def __init__(self, settings: Settings):
        headers = {"Host": settings.http_host_header} if settings.http_host_header else {}
        self._http = httpx.AsyncClient(timeout=15, headers=headers)
        self._prometheus = settings.prometheus_url

    async def firing(self) -> list[str]:
        response = await self._http.get(
            f"{self._prometheus}/api/v1/query", params={"query": 'ALERTS{stand="voting",alertstate="firing"}'}
        )
        return sorted({r["metric"]["alertname"] for r in response.json()["data"]["result"]})

    async def settle(self, quiet_s: int = 60, timeout_s: int = 900) -> list[str]:
        """Waits until no voting alert has fired for quiet_s seconds; returns whatever still fires at the timeout."""
        deadline, quiet_since = time.monotonic() + timeout_s, time.monotonic()
        while time.monotonic() < deadline:
            if await self.firing():
                quiet_since = time.monotonic()
            elif time.monotonic() - quiet_since >= quiet_s:
                return []
            await asyncio.sleep(10)
        return await self.firing()

    async def silence(self, hours: float) -> str:
        now = datetime.now(UTC)
        body = {
            "matchers": [{"name": "stand", "value": "voting", "isRegex": False, "isEqual": True}],
            "startsAt": now.isoformat(),
            "endsAt": (now + timedelta(hours=hours)).isoformat(),
            "createdBy": "ai-sre-backtest",
            "comment": "backtest running: the runner investigates, not the agent in the cluster",
        }
        response = await self._http.post(f"{ALERTMANAGER_URL}/api/v2/silences", json=body)
        response.raise_for_status()
        return str(response.json()["silenceID"])

    async def unsilence(self, silence_id: str) -> None:
        await self._http.delete(f"{ALERTMANAGER_URL}/api/v2/silence/{silence_id}")

    async def aclose(self) -> None:
        await self._http.aclose()


async def _payload(alert: str, settings: Settings, wait_s: int = 90) -> dict[str, Any]:
    """The alert as Alertmanager would post it; Prometheus may need a moment to hand it to Alertmanager."""
    deadline = time.monotonic() + wait_s
    while True:
        try:
            return await webhook_payload(alert, settings)
        except SystemExit:
            if time.monotonic() > deadline:
                raise
            await asyncio.sleep(5)


def _seconds_between(start: str, end: str) -> float | None:
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round((b - a).total_seconds(), 1)


async def run_scenario(name: str, run: int, settings: Settings, stand: Stand, out: Path, agent: str) -> Result:
    log = out / "logs" / f"{name}-{run}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    still = await stand.settle()
    if still:
        print(f"  warning: still firing before {name}: {', '.join(still)}", flush=True)
    directory = SCENARIOS_DIR / name
    try:
        await asyncio.to_thread(run_script, directory / "break.sh", log)
        expected = yaml.safe_load((SCENARIOS_DIR / ".state" / f"{name}.expected.yaml").read_text(encoding="utf-8"))
        payload = await _payload(expected["alert"], settings)
        inv = await (rules.run if agent == "rules" else investigator.run)(payload, settings)
    finally:
        await asyncio.to_thread(run_script, directory / "restore.sh", log)

    rank, triage_ok = score(inv, expected)
    return Result(
        scenario=name,
        run=run,
        alert=expected["alert"],
        expected_triage=str(expected.get("triage")),
        correct_rank=rank,
        top1=rank == 1,
        top3=rank is not None,
        triage=inv.triage,
        triage_ok=triage_ok,
        confidence=inv.confidence,
        hypotheses=inv.hypotheses,
        alert_to_answer_s=_seconds_between(inv.alert_started_at, inv.finished_at),
        investigation_s=inv.duration_s,
        tokens=inv.tokens,
        cost_usd=inv.cost_usd,
        steps=inv.steps,
        tool_calls=inv.tool_calls,
        stopped_by=inv.stopped_by,
        model=inv.model,
        prompt_version=inv.prompt_version,
        audit_path=inv.audit_path,
        error=inv.error,
    )


def summary(results: list[Result], label: str) -> str:
    def yes(value: bool) -> str:
        return "✅" if value else "❌"

    lines = [
        f"# Backtest {label}",
        "",
        f"Model `{results[0].model}`, prompt `{results[0].prompt_version}`." if results else "No results.",
        "",
        "| Scenario | Alert | Top-1 | Top-3 | Triage (expected → got) | Confidence | Alert → answer | Investigation"
        " | Tokens | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.scenario} #{r.run} | {r.alert} | {yes(r.top1)} | {yes(r.top3)} | {r.expected_triage} → {r.triage}"
            f" {yes(r.triage_ok)} | {r.confidence} | {r.alert_to_answer_s}s | {r.investigation_s}s | {r.tokens}"
            f" | ${r.cost_usd:.4f} |"
        )
    if results:
        n = len(results)
        answers = [r.alert_to_answer_s for r in results if r.alert_to_answer_s is not None]
        wrong_but_sure = sum(1 for r in results if not r.top1 and r.confidence == "high")
        lines += [
            "",
            f"- **Top-1**: {sum(r.top1 for r in results)}/{n}, **top-3**: {sum(r.top3 for r in results)}/{n},"
            f" **triage**: {sum(r.triage_ok for r in results)}/{n}",
            f'- **Wrong but "high" confidence**: {wrong_but_sure}/{n}',
            f"- **Median alert → answer**: {statistics.median(answers) if answers else 'n/a'}s,"
            f" median investigation {statistics.median(r.investigation_s for r in results)}s",
            f"- **Median cost**: ${statistics.median(r.cost_usd for r in results):.4f},"
            f" total ${sum(r.cost_usd for r in results):.4f},"
            f" median tokens {statistics.median(r.tokens for r in results)}",
        ]
    return "\n".join(lines) + "\n"


async def main_async(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    scenarios = [s for s in ALL if any(s.startswith(p) for p in args.scenarios.split(","))] if args.scenarios else ALL
    out = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    stand = Stand(settings)
    silence = None if args.no_silence else await stand.silence(hours=6)
    results: list[Result] = []
    try:
        for run in range(1, args.runs + 1):
            for name in scenarios:
                print(f"{name} #{run} ...", flush=True)
                try:
                    result = await run_scenario(name, run, settings, stand, out, args.agent)
                except Exception as exc:  # a scenario that cannot run is reported, the others still run
                    print(f"  FAILED: {exc}", flush=True)
                    (out / "errors.log").open("a", encoding="utf-8").write(f"{name} #{run}: {exc}\n")
                    continue
                results.append(result)
                with (out / "results.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
                print(
                    f"  top-1 {result.top1}, top-3 {result.top3}, triage {result.triage} ({result.triage_ok}),"
                    f" {result.alert_to_answer_s}s, ${result.cost_usd:.4f}: {result.hypotheses[:1]}",
                    flush=True,
                )
                (out / "summary.md").write_text(summary(results, args.label), encoding="utf-8")
    finally:
        if silence:
            await stand.unsilence(silence)
        await stand.aclose()
    print(summary(results, args.label))
    print(f"results in {out}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the agent on the chaos scenarios.")
    parser.add_argument("--scenarios", default="", help="comma-separated prefixes, e.g. 01,08 (default: all)")
    parser.add_argument("--runs", type=int, default=1, help="how many times to run each scenario")
    parser.add_argument("--label", default="baseline", help="a name for this run, part of the results directory")
    parser.add_argument("--agent", choices=["llm", "rules"], default="llm", help="the LLM agent or the rule baseline")
    parser.add_argument("--no-silence", action="store_true", help="let the agent in the cluster answer too")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
