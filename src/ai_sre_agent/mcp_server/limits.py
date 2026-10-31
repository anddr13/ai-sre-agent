"""Validation and size limits shared by the tools. Everything the model passes in goes through here first."""

import asyncio
import re
from collections.abc import Awaitable
from datetime import timedelta
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

DURATION = re.compile(r"^(\d{1,4})([smhd])$")
UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
# Kubernetes object and namespace names (RFC 1123 labels/subdomains).
K8S_NAME = re.compile(r"^[a-z0-9]([-a-z0-9.]{0,251}[a-z0-9])?$")
# A path inside the GitOps repo: no option-like or parent-directory tricks.
REPO_PATH = re.compile(r"^[\w][\w./-]{0,199}$")
# Environment variables whose plain values are not shown even though the agent may read the object.
SENSITIVE_NAME = re.compile(r"PASS|SECRET|TOKEN|KEY|CREDENTIAL|AUTH", re.IGNORECASE)

MAX_TEXT = 400  # characters of one log line or message


def parse_duration(value: str, *, maximum: timedelta, name: str = "duration") -> timedelta:
    """'90s', '15m', '6h', '2d' -> timedelta, refusing anything above maximum."""
    match = DURATION.match(value.strip())
    if not match:
        raise ToolError(f"{name} must look like 30s, 15m, 6h or 2d, got {value!r}")
    amount, unit = int(match.group(1)), match.group(2)
    delta = timedelta(**{UNITS[unit]: amount})
    if delta <= timedelta(0) or delta > maximum:
        raise ToolError(f"{name} must be between 1s and {_human(maximum)}, got {value!r}")
    return delta


def check_k8s_name(value: str, what: str) -> str:
    if not K8S_NAME.match(value):
        raise ToolError(f"{what} {value!r} is not a valid Kubernetes name")
    return value


def check_namespace(value: str, allowed: tuple[str, ...]) -> str:
    check_k8s_name(value, "namespace")
    if value not in allowed:
        raise ToolError(f"namespace {value!r} is not allowed; allowed: {', '.join(allowed)}")
    return value


def check_repo_path(value: str) -> str:
    if not REPO_PATH.match(value) or ".." in value.split("/"):
        raise ToolError(f"path {value!r} is not a plain path inside the repository")
    return value


def clamp(value: int, low: int, high: int, name: str) -> int:
    if not low <= value <= high:
        raise ToolError(f"{name} must be between {low} and {high}, got {value}")
    return value


def shorten(text: str, limit: int = MAX_TEXT) -> str:
    return text if len(text) <= limit else f"{text[:limit]}... [{len(text) - limit} more characters]"


async def with_timeout[T](call: Awaitable[T], seconds: float, what: str) -> T:
    try:
        return await asyncio.wait_for(call, seconds)
    except TimeoutError as exc:
        raise ToolError(f"{what} did not answer within {seconds:g}s") from exc


def redact_env(env: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Container env as name + value, or name + where it comes from; sensitive plain values are hidden."""
    result = []
    for var in env or []:
        name = var.get("name", "")
        if "valueFrom" in var:
            result.append({"name": name, "valueFrom": var["valueFrom"]})
        elif SENSITIVE_NAME.search(name):
            result.append({"name": name, "value": "[redacted]"})
        else:
            result.append({"name": name, "value": var.get("value", "")})
    return result


def _human(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds % size == 0 and seconds >= size:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"
