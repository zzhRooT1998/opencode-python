"""Public retrieval service used by planner and executor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from opencode_py.retrieval.indexer import CodeChunk, RepositoryIndexer
from opencode_py.retrieval.ranker import HeuristicReranker, KeywordRanker


@dataclass(slots=True)
class RetrievalHit:
    """Ranked evidence pack entry."""

    path: str
    line_start: int
    line_end: int
    snippet: str
    score: float
    reason: str
    symbol: str | None = None


class RetrievalService:
    """Index and retrieve relevant code snippets for a task query."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        indexer: RepositoryIndexer | None = None,
        ranker: KeywordRanker | None = None,
        reranker: HeuristicReranker | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.indexer = indexer or RepositoryIndexer(self.workspace_root)
        self.ranker = ranker or KeywordRanker()
        self.reranker = reranker or HeuristicReranker()
        self._chunks: list[CodeChunk] | None = None

    def refresh(self) -> list[CodeChunk]:
        """Rebuild and cache the repository chunk index."""

        self._chunks = self.indexer.build()
        return self._chunks

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        """Return top-ranked retrieval hits for a task query."""

        chunks = self._chunks if self._chunks is not None else self.refresh()
        candidates = [
            (chunk, self.ranker.score(query, chunk))
            for chunk in chunks
        ]
        scored = [(chunk, score) for chunk, score in candidates if score > 0]
        reranked = self.reranker.rerank(query, scored)
        return [
            RetrievalHit(
                path=chunk.path,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                snippet=chunk.content,
                score=score,
                reason=_reason(query, chunk),
                symbol=chunk.symbol,
            )
            for chunk, score in reranked[:top_k]
        ]


def _reason(query: str, chunk: CodeChunk) -> str:
    if chunk.symbol and chunk.symbol.lower() in query.lower():
        return f"Matched symbol `{chunk.symbol}`."
    if chunk.path.lower() in query.lower():
        return "Matched file path."
    return "Matched lexical overlap from query terms."

