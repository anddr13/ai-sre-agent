"""git log of the GitOps repository: what changed in the desired state, when, and by whom.

git runs as a subprocess with a fixed argument list (no shell); the only inputs from the model are a
validated duration, validated paths and numbers.
"""

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from .limits import shorten

MAX_DIFF = 4000  # characters of diff per commit
FIELD = "\x1f"
RECORD = "\x1e"


async def _git(repo: str, *args: str, timeout_s: float) -> str:
    process = await asyncio.create_subprocess_exec(
        "git", "-C", repo, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_s)
    except TimeoutError as exc:
        process.kill()
        raise ToolError(f"git {args[0]} did not finish within {timeout_s:g}s") from exc
    if process.returncode != 0:
        raise ToolError(f"git {args[0]} failed: {shorten(stderr.decode(errors='replace'), 300)}")
    return stdout.decode(errors="replace")


async def gitops_log(
    repo: str,
    branch: str,
    since: timedelta,
    paths: list[str],
    max_count: int,
    with_diff: bool,
    timeout_s: float,
) -> dict[str, Any]:
    if not (Path(repo) / ".git").exists():
        raise ToolError(f"GitOps repository not found at {repo}")
    # Bring the remote branch up to date; if that fails (offline) the local copy is still worth reading.
    fetched = True
    try:
        await _git(repo, "fetch", "--quiet", "origin", branch, timeout_s=timeout_s / 2)
    except ToolError:
        fetched = False

    ref = f"origin/{branch}"
    args = [
        "log",
        ref,
        f"--since={int(since.total_seconds())} seconds ago",
        f"--max-count={max_count}",
        f"--format={RECORD}%H{FIELD}%an{FIELD}%aI{FIELD}%s",
        "--name-only",
    ]
    if paths:
        args += ["--", *paths]  # commits touching any of them
    out = await _git(repo, *args, timeout_s=timeout_s)

    commits = []
    for record in out.split(RECORD)[1:]:
        header, _, files = record.partition("\n")
        sha, author, date, subject = header.split(FIELD)
        commits.append(
            {
                "sha": sha[:12],
                "author": author,
                "date": date,
                "subject": subject,
                "files": [f for f in files.splitlines() if f],
            }
        )
    if with_diff:
        for commit in commits:
            diff = await _git(repo, "show", "--format=", "--unified=1", commit["sha"], timeout_s=timeout_s)
            commit["diff"] = shorten(diff, MAX_DIFF)
    return {
        "repository": repo,
        "branch": ref,
        "fetched": fetched,
        "commits_newest_first": commits,
    }
