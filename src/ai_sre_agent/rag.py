"""RAG over the runbooks: the runbooks most similar to the alert go into the agent's first message.

Each runbook is cut at its `## ` sections; every section is embedded on the CPU (fastembed, bge-small, no external
call) and stored in pgvector in the agent's own Postgres (ai-sre-db, database agent). A runbook's score is the
similarity of its best section; the top runbooks go to the model whole. Only the runbooks are in the corpus, never
past investigations, so the backtest cannot "remember" an answer.

    uv run ai-sre-rag sync      # make the table match runbooks/ (only changed sections are embedded)
    uv run ai-sre-rag search "PostgresConnectionsHigh too many clients"
"""

import argparse
import asyncio
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg

from ai_sre_agent.config import REPO_ROOT, Settings

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
RUNBOOKS_DIR = REPO_ROOT / "runbooks"
SECTIONS_PER_QUERY = 12  # enough sections to rank the runbooks they belong to

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS runbook_sections (
    source      text NOT NULL,
    position    int NOT NULL,
    heading     text NOT NULL,
    content     text NOT NULL,
    content_sha text NOT NULL,
    model       text NOT NULL,
    embedding   vector({DIMENSIONS}) NOT NULL,
    PRIMARY KEY (source, position)
)
"""


@dataclass(frozen=True)
class Section:
    source: str  # the runbook's file name without .md, i.e. the alert name
    position: int
    heading: str
    content: str

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

    @property
    def text_to_embed(self) -> str:
        return f"{self.source}: {self.heading}\n{self.content}"


@dataclass
class Runbook:
    source: str
    score: float
    text: str


def sections(path: Path) -> list[Section]:
    """The runbook up to the first `## ` (title and symptom), then one section per `## ` heading."""
    source = path.stem
    parts = re.split(r"(?m)^## ", path.read_text(encoding="utf-8"))
    result = [Section(source, 0, "Symptom", parts[0].strip())]
    for position, part in enumerate(parts[1:], start=1):
        heading = part.partition("\n")[0]
        result.append(Section(source, position, heading.strip(), f"## {part.strip()}"))
    return [s for s in result if s.content]


def corpus(directory: Path = RUNBOOKS_DIR) -> list[Section]:
    return [s for path in sorted(directory.glob("*.md")) for s in sections(path)]


class Embedder:
    """bge-small on the CPU; the model is loaded on first use (from the image, or downloaded once into the cache)."""

    def __init__(self, cache_dir: str):
        self._cache_dir = cache_dir
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding  # slow import; only when RAG is used

            # One thread and small batches: 390 MB peak instead of 600 MB, and the corpus is tiny anyway.
            self._model = TextEmbedding(EMBEDDING_MODEL, cache_dir=self._cache_dir, threads=1)
        return self._model

    async def documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(lambda: [v.tolist() for v in self._load().embed(texts, batch_size=4)])

    async def query(self, text: str) -> list[float]:
        return await asyncio.to_thread(lambda: next(iter(self._load().query_embed(text))).tolist())


_embedders: dict[str, Embedder] = {}


def embedder(cache_dir: str) -> Embedder:
    """One model per process: loading it takes seconds."""
    return _embedders.setdefault(cache_dir, Embedder(cache_dir))


async def _connect(database_url: str, attempts: int = 3) -> asyncpg.Connection:
    """A connection, retried briefly: a restarting database or port-forward refuses for a second or two."""
    for attempt in range(1, attempts + 1):
        try:
            return await asyncpg.connect(database_url, timeout=10)
        except OSError:
            if attempt == attempts:
                raise
            await asyncio.sleep(2)
    raise AssertionError("unreachable")


def _vector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


async def sync(database_url: str, embedder: Embedder, wanted: list[Section]) -> tuple[int, int]:
    """Make the table match `wanted`; returns (sections embedded, rows deleted)."""
    conn = await _connect(database_url)
    try:
        await conn.execute(SCHEMA)
        rows = await conn.fetch("SELECT source, position, content_sha, model FROM runbook_sections")
        have = {(r["source"], r["position"]): (r["content_sha"], r["model"]) for r in rows}
        changed = [s for s in wanted if have.get((s.source, s.position)) != (s.sha, EMBEDDING_MODEL)]
        vectors = await embedder.documents([s.text_to_embed for s in changed]) if changed else []
        stale = set(have) - {(s.source, s.position) for s in wanted}
        async with conn.transaction():
            for s, vector in zip(changed, vectors, strict=True):
                await conn.execute(
                    """INSERT INTO runbook_sections (source, position, heading, content, content_sha, model, embedding)
                       VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                       ON CONFLICT (source, position) DO UPDATE SET heading = $3, content = $4, content_sha = $5,
                           model = $6, embedding = $7::vector""",
                    s.source, s.position, s.heading, s.content, s.sha, EMBEDDING_MODEL, _vector(vector),
                )  # fmt: skip
            for source, position in stale:
                await conn.execute("DELETE FROM runbook_sections WHERE source = $1 AND position = $2", source, position)
        return len(changed), len(stale)
    finally:
        await conn.close()


async def search(database_url: str, embedder: Embedder, query: str, top_k: int) -> list[Runbook]:
    """The `top_k` runbooks whose best section is closest to the query (cosine similarity)."""
    conn = await _connect(database_url)  # first: a dead database fails before the model loads
    try:
        vector = _vector(await embedder.query(query))
        hits = await conn.fetch(
            """SELECT source, 1 - (embedding <=> $1::vector) AS score FROM runbook_sections
               ORDER BY embedding <=> $1::vector LIMIT $2""",
            vector,
            SECTIONS_PER_QUERY,
        )
        best: dict[str, float] = {}
        for hit in hits:  # nearest first, so the first hit of a runbook is its best section
            best.setdefault(hit["source"], float(hit["score"]))
        sources = list(best)[:top_k]
        rows = await conn.fetch(
            "SELECT source, content FROM runbook_sections WHERE source = ANY($1::text[]) ORDER BY source, position",
            sources,
        )
    finally:
        await conn.close()
    texts: dict[str, list[str]] = {}
    for row in rows:
        texts.setdefault(row["source"], []).append(row["content"])
    return [Runbook(s, round(best[s], 3), "\n\n".join(texts.get(s, []))) for s in sources]


def context(runbooks: list[Runbook]) -> str:
    """How the retrieved runbooks are shown to the model: as background, not as evidence."""
    if not runbooks:
        return ""
    parts = [
        "Runbooks retrieved by similarity to the alert. They list typical causes and checks; they are not evidence "
        "about this incident and may not apply. Verify with the tools before you rely on them."
    ]
    parts += [f"--- runbook {r.source} (similarity {r.score}) ---\n{r.text}" for r in runbooks]
    return "\n\n".join(parts)


async def main_async(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    if not settings.rag_database_url:
        raise SystemExit("RAG_DATABASE_URL is not set")
    model = embedder(settings.embedding_cache_dir)
    if args.command == "sync":
        embedded, deleted = await sync(settings.rag_database_url, model, corpus())
        print(f"{embedded} sections embedded, {deleted} deleted")
    else:
        for r in await search(settings.rag_database_url, model, args.query, settings.rag_top_k):
            print(f"{r.score:.3f}  {r.source}")


def main() -> None:
    parser = argparse.ArgumentParser(description="The runbook corpus of the agent's RAG.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync", help="embed the runbooks that changed and store them in pgvector")
    commands.add_parser("search", help="the runbooks closest to a text").add_argument("query")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
