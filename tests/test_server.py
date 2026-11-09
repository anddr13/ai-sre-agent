"""The MCP surface: what the model sees, and that bad arguments are refused before anything is called."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from ai_sre_agent.config import Settings
from ai_sre_agent.mcp_server.server import build_server

EXPECTED_TOOLS = {
    "prometheus_query",
    "loki_query",
    "k8s_events",
    "k8s_describe",
    "argocd_app_history",
    "gitops_log",
}


@pytest.fixture
def server(tmp_path: Path) -> Any:
    # Endpoints nobody listens on: a validation error must come before any network or Kubernetes call.
    settings = Settings(
        prometheus_url="http://127.0.0.1:9",
        loki_url="http://127.0.0.1:9",
        agent_kubeconfig=str(tmp_path / "missing-kubeconfig"),
        gitops_repo=str(tmp_path),
        tool_timeout_s=2,
    )
    return build_server(settings)


async def test_exactly_the_six_read_only_tools(server: Any) -> None:
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.description


@pytest.mark.parametrize(
    ("tool", "arguments", "message"),
    [
        ("prometheus_query", {"query": "up", "lookback": "7d"}, "lookback"),
        ("loki_query", {"query": '{a="b"}', "limit": 5000}, "limit"),
        ("k8s_events", {"namespace": "kube-system"}, "not allowed"),
        ("k8s_describe", {"kind": "secret", "namespace": "voting", "name": "voting-pg-app"}, "kind"),
        ("k8s_describe", {"kind": "pod", "namespace": "voting", "name": "../../etc"}, "not a valid"),
        ("argocd_app_history", {"app": "Voting!"}, "not a valid"),
        ("gitops_log", {"path": "../../.ssh"}, "not a plain path"),
        ("gitops_log", {"path": "charts/voting,../../.ssh"}, "not a plain path"),
        ("gitops_log", {"path": "a,b,c,d,e,f"}, "at most 5 paths"),
        ("gitops_log", {"since": "30d"}, "since"),
    ],
)
async def test_bad_arguments_are_refused(server: Any, tool: str, arguments: dict[str, Any], message: str) -> None:
    async with Client(server) as client:
        result = await client.call_tool(tool, arguments)
    assert result.is_error
    assert message in result.content[0].text


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


async def test_comma_separated_paths_are_several_paths(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "lab")
    for name in ("values.yaml", "local.yaml", "other.yaml"):
        (origin / name).write_text(name, encoding="utf-8")
        git(origin, "add", name)
        git(origin, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"change {name}")
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    settings = Settings(gitops_repo=str(clone), gitops_branch="lab", tool_timeout_s=10)
    async with Client(build_server(settings)) as client:
        result = await client.call_tool("gitops_log", {"path": "values.yaml, local.yaml"})
    assert not result.is_error, result.content[0].text
    subjects = [c["subject"] for c in json.loads(result.content[0].text)["commits_newest_first"]]
    assert subjects == ["change local.yaml", "change values.yaml"]


async def test_unreachable_backend_is_a_clean_error(server: Any) -> None:
    async with Client(server) as client:
        result = await client.call_tool("prometheus_query", {"query": "up"})
    assert result.is_error
    # Refused connection or a port that swallows the SYN (Windows): either way a message, not a crash.
    assert "unreachable" in result.content[0].text or "did not answer" in result.content[0].text
