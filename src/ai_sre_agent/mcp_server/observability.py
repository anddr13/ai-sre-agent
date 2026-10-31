"""Prometheus (PromQL) and Loki (LogQL) over their HTTP APIs, read-only, with bounded answers."""

import time
from datetime import timedelta
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from .limits import shorten

MAX_SERIES = 30
MAX_POINTS = 60  # per series in a range query; longer series are thinned out evenly
MAX_LOG_LINES = 300


class HttpApi:
    """An HTTP client created on first use and dropped by aclose(), so the server survives several sessions."""

    def __init__(self, base_url: str, host_header: str, timeout: float):
        self._base_url = base_url
        self._headers = {"Host": host_header} if host_header else {}
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, headers=self._headers, timeout=self._timeout)
        try:
            response = await self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise ToolError(f"{self._base_url} unreachable: {exc!r}") from exc
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code != 200 or body.get("status") not in (None, "success"):
            error = body.get("error") or shorten(response.text, 300)
            raise ToolError(f"HTTP {response.status_code}: {error}")
        return body.get("data", body)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def _thin(values: list[Any], limit: int) -> list[Any]:
    if len(values) <= limit:
        return values
    step = len(values) / limit
    picked = [values[int(i * step)] for i in range(limit - 1)]
    return [*picked, values[-1]]  # always keep the newest point


def _series(data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("result", [])
    kind = data.get("resultType")
    out: dict[str, Any] = {
        "result_type": kind,
        "series_total": len(result) if isinstance(result, list) else 1,
    }
    if kind == "matrix":
        out["series"] = [
            {"labels": s.get("metric", {}), "values": _thin(s.get("values", []), MAX_POINTS)}
            for s in result[:MAX_SERIES]
        ]
    elif kind == "vector":
        out["series"] = [{"labels": s.get("metric", {}), "value": s.get("value")} for s in result[:MAX_SERIES]]
    else:  # scalar or string
        out["value"] = result
    if isinstance(result, list) and len(result) > MAX_SERIES:
        out["truncated"] = f"showing {MAX_SERIES} of {len(result)} series; aggregate with sum by (...) or topk"
    return out


async def prometheus_query(
    api: HttpApi, query: str, window: timedelta | None, step: timedelta | None
) -> dict[str, Any]:
    now = time.time()
    if window is None:
        data = await api.get("/api/v1/query", {"query": query, "time": now})
    else:
        # Aim for about MAX_POINTS points unless a step was given.
        step_s = step.total_seconds() if step else max(15, int(window.total_seconds() / MAX_POINTS))
        data = await api.get(
            "/api/v1/query_range",
            {"query": query, "start": now - window.total_seconds(), "end": now, "step": step_s},
        )
    return {"query": query, **_series(data)}


async def loki_query(api: HttpApi, query: str, since: timedelta, limit: int) -> dict[str, Any]:
    now_ns = time.time_ns()
    data = await api.get(
        "/loki/api/v1/query_range",
        {
            "query": query,
            "start": now_ns - int(since.total_seconds() * 1e9),
            "end": now_ns,
            "limit": limit,
            "direction": "backward",
        },
    )
    if data.get("resultType") != "streams":  # a metric query such as count_over_time(...)
        return {"query": query, **_series(data)}

    lines = []
    for stream in data.get("result", []):
        labels = stream.get("stream", {})
        source = {k: labels[k] for k in ("namespace", "pod", "container") if k in labels}
        for ts, line in stream.get("values", []):
            lines.append({"ts_ns": int(ts), **source, "line": shorten(line)})
    lines.sort(key=lambda entry: entry["ts_ns"], reverse=True)
    lines = lines[:limit]
    for entry in lines:
        entry["time"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry.pop("ts_ns") / 1e9))
    return {"query": query, "lines_returned": len(lines), "newest_first": lines}
