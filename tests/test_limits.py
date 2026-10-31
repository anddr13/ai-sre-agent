from datetime import timedelta

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from ai_sre_agent.mcp_server.limits import (
    check_k8s_name,
    check_namespace,
    check_repo_path,
    clamp,
    parse_duration,
    redact_env,
    shorten,
)

SIX_HOURS = timedelta(hours=6)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("90s", timedelta(seconds=90)), ("15m", timedelta(minutes=15)), ("6h", SIX_HOURS), (" 2h ", timedelta(hours=2))],
)
def test_parse_duration(text: str, expected: timedelta) -> None:
    assert parse_duration(text, maximum=SIX_HOURS) == expected


@pytest.mark.parametrize("text", ["7h", "1w", "15", "-5m", "0m", "1.5h", "15m; rm -rf /"])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(ToolError):
        parse_duration(text, maximum=SIX_HOURS)


def test_namespace_must_be_allowed() -> None:
    assert check_namespace("voting", ("voting",)) == "voting"
    with pytest.raises(ToolError, match="not allowed"):
        check_namespace("kube-system", ("voting",))


@pytest.mark.parametrize("name", ["Voting", "a_b", "x/../y", "-leading", "a" * 300])
def test_k8s_name_rejects(name: str) -> None:
    with pytest.raises(ToolError):
        check_k8s_name(name, "name")


@pytest.mark.parametrize("path", ["charts/voting", "envs/local.yaml"])
def test_repo_path(path: str) -> None:
    assert check_repo_path(path) == path


@pytest.mark.parametrize("path", ["../secrets", "charts/../../x", "--output=x", "/etc/passwd", "a b"])
def test_repo_path_rejects(path: str) -> None:
    with pytest.raises(ToolError):
        check_repo_path(path)


def test_clamp() -> None:
    assert clamp(5, 1, 10, "n") == 5
    with pytest.raises(ToolError):
        clamp(11, 1, 10, "n")


def test_shorten() -> None:
    assert shorten("abc", 5) == "abc"
    assert shorten("a" * 10, 4) == "aaaa... [6 more characters]"


def test_redact_env_hides_sensitive_plain_values() -> None:
    env = [
        {"name": "KAFKA_BROKERS", "value": "kafka:9092"},
        {"name": "PGPASSWORD", "valueFrom": {"secretKeyRef": {"name": "voting-pg-app", "key": "password"}}},
        {"name": "API_TOKEN", "value": "s3cr3t"},
        {"name": "DB_PASS", "value": "hunter2"},
    ]
    assert redact_env(env) == [
        {"name": "KAFKA_BROKERS", "value": "kafka:9092"},
        {"name": "PGPASSWORD", "valueFrom": {"secretKeyRef": {"name": "voting-pg-app", "key": "password"}}},
        {"name": "API_TOKEN", "value": "[redacted]"},
        {"name": "DB_PASS", "value": "[redacted]"},
    ]
