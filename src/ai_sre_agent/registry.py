"""Backtest results into a lasting MLflow, and the best configuration's prompts into its Prompt Registry.

The cloud stands (cloud/) each have an MLflow of their own that goes away with the machine; their result
directories come back with `cloud/stands.sh collect`. This logs them again, by default into a SQLite file in the
repository (mlflow.db, not in git):

    uv run ai-sre-mlflow import                        # every result directory with params.json, once each
    uv run ai-sre-mlflow compare --label-prefix abl-   # the configurations over their repeats
    uv run ai-sre-mlflow register --label-prefix abl-  # the best one's prompts, alias "best"
    uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
"""

import argparse
import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mlflow

from ai_sre_agent import investigator, team
from ai_sre_agent.backtest import RESULTS_DIR, Result, _scenario_metrics, totals
from ai_sre_agent.config import REPO_ROOT

EXPERIMENT = "ai-sre-backtest"
DEFAULT_URI = f"sqlite:///{(REPO_ROOT / 'mlflow.db').as_posix()}"
DEFAULT_ARTIFACTS = REPO_ROOT / "mlartifacts"
# What two runs must share to be repeats of one configuration.
CONFIG_KEYS = ("agent", "model", "verifier_model", "rag", "prompt_version", "apply_fix")
SCORES = ("top1", "top3", "triage", "wrong_but_sure", "recovered")


@dataclass
class Backtest:
    directory: Path
    params: dict[str, Any]
    results: list[Result]

    @property
    def config(self) -> tuple[Any, ...]:
        return tuple(self.params.get(k) for k in CONFIG_KEYS)


@dataclass
class Config:
    params: dict[str, Any]
    runs: list[Backtest] = field(default_factory=list)

    def scores(self) -> dict[str, float]:
        """Mean over the repeats; every repeat is the full set of scenarios."""
        per_run = [totals(b.results) for b in self.runs]
        return {k: statistics.mean(t.get(k, 0) for t in per_run) for k in SCORES}

    def rank(self) -> tuple[float, ...]:
        """Best first: the cause found first, then few wrong answers given with confidence, then the triage."""
        s = self.scores()
        return (s["top1"], -s["wrong_but_sure"], s["triage"], s["recovered"])


def load(directory: Path) -> Backtest | None:
    """A result directory with params.json (backtests since 2026-11-07) and at least one result."""
    params_file, results_file = directory / "params.json", directory / "results.jsonl"
    if not params_file.exists() or not results_file.exists():
        return None
    params = json.loads(params_file.read_text(encoding="utf-8"))
    lines = results_file.read_text(encoding="utf-8").splitlines()
    results = [Result(**json.loads(line)) for line in lines if line.strip()]
    return Backtest(directory, params, results) if results else None


def backtests(label_prefix: str = "", results_dir: Path = RESULTS_DIR) -> list[Backtest]:
    found = [load(d) for d in sorted(results_dir.iterdir()) if d.is_dir()]
    return [b for b in found if b and str(b.params.get("label", "")).startswith(label_prefix)]


def configs(runs: list[Backtest]) -> list[Config]:
    """Repeats grouped by configuration, best first."""
    grouped: dict[tuple[Any, ...], Config] = {}
    for b in runs:
        grouped.setdefault(b.config, Config({k: b.params.get(k) for k in CONFIG_KEYS})).runs.append(b)
    return sorted(grouped.values(), key=Config.rank, reverse=True)


def import_runs(runs: list[Backtest], artifacts: Path = DEFAULT_ARTIFACTS) -> int:
    """Logs every backtest that is not in the experiment yet (tag results_dir); returns how many."""
    # Artifacts next to the database, not in ./mlruns of whatever directory this runs in.
    if mlflow.get_experiment_by_name(EXPERIMENT) is None:
        mlflow.create_experiment(EXPERIMENT, artifact_location=artifacts.resolve().as_uri())
    mlflow.set_experiment(EXPERIMENT)
    imported = 0
    for b in runs:
        name = b.directory.name
        if not mlflow.search_runs(experiment_names=[EXPERIMENT], filter_string=f"tags.results_dir = '{name}'").empty:
            continue
        params = {k: v for k, v in b.params.items() if k != "label"}
        with mlflow.start_run(run_name=b.params.get("label", name), tags={"results_dir": name, "source": "import"}):
            mlflow.log_params(params)
            for r in b.results:
                mlflow.log_metrics(_scenario_metrics(r), step=r.run)
            mlflow.log_metrics(totals(b.results))
            for artifact in ("summary.md", "results.jsonl", "errors.log", "params.json"):
                if (b.directory / artifact).exists():
                    mlflow.log_artifact(str(b.directory / artifact))
        imported += 1
    return imported


def prompts_of(agent: str) -> dict[str, str]:
    """The registry entries of an agent: one prompt for the single agent, two for the team."""
    if agent == "team":
        return {"ai-sre-investigator": team.INVESTIGATOR_PROMPT, "ai-sre-verifier": team.VERIFIER_PROMPT}
    return {"ai-sre-agent": investigator.SYSTEM_PROMPT}


def current_prompt_version(agent: str) -> str:
    return team.PROMPT_VERSION if agent == "team" else investigator.PROMPT_VERSION


def register(best: Config) -> dict[str, int]:
    """The best configuration's prompts, with the model and the scores as tags and the alias "best"."""
    agent = str(best.params["agent"])
    if best.params["prompt_version"] != current_prompt_version(agent):
        raise SystemExit(
            f"the prompt changed since these runs ({best.params['prompt_version']} -> "
            f"{current_prompt_version(agent)}): check out their commit to register them"
        )
    scores = best.scores()
    tags = {k: str(v) for k, v in best.params.items()} | {f"mean_{k}": f"{v:.2f}" for k, v in scores.items()}
    tags |= {"repeats": str(len(best.runs)), "results_dirs": ",".join(b.directory.name for b in best.runs)}
    versions = {}
    for name, template in prompts_of(agent).items():
        version = mlflow.genai.register_prompt(
            name=name, template=template, commit_message=f"best of the backtest: {tags['results_dirs']}", tags=tags
        )
        mlflow.genai.set_prompt_alias(name, alias="best", version=version.version)
        versions[name] = version.version
    return versions


def table(found: list[Config]) -> str:
    lines = ["| agent | verifier | RAG | repeats | " + " | ".join(SCORES) + " |", "|---" * (4 + len(SCORES)) + "|"]
    for c in found:
        s = c.scores()
        verifier = c.params["verifier_model"] or "-"
        lines.append(
            f"| {c.params['agent']} | {verifier} | {c.params['rag']} | {len(c.runs)} | "
            + " | ".join(f"{s[k]:.2f}" for k in SCORES)
            + " |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["import", "compare", "register"])
    parser.add_argument("--label-prefix", default="", help="only the backtests whose label starts with this")
    parser.add_argument("--tracking-uri", default=DEFAULT_URI)
    args = parser.parse_args()
    runs = backtests(args.label_prefix)
    if args.command == "compare":
        print(table(configs(runs)))
        return
    mlflow.set_tracking_uri(args.tracking_uri)
    if args.command == "import":
        print(f"imported {import_runs(runs)} of {len(runs)} backtests into {args.tracking_uri}")
        return
    found = configs(runs)
    if not found:
        raise SystemExit("no backtests with params.json match")
    print(table(found))
    print(f"registered: {register(found[0])}")
