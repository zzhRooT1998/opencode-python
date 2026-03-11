"""Ranking helpers for retrieval candidates."""

from __future__ import annotations

import math
import re
from collections import Counter

from opencode_py.retrieval.indexer import CodeChunk


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


class KeywordRanker:
    """Lightweight lexical ranker with BM25-style saturation."""

    def score(self, query: str, chunk: CodeChunk) -> float:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return 0.0

        chunk_tokens = _tokenize(f"{chunk.path}\n{chunk.symbol or ''}\n{chunk.content}")
        if not chunk_tokens:
            return 0.0

        term_counts = Counter(chunk_tokens)
        score = 0.0
        for token in query_tokens:
            tf = term_counts[token]
            if tf == 0:
                continue
            score += ((1.2 + 1) * tf) / (1.2 + tf)

        overlap = len(set(query_tokens) & set(chunk_tokens))
        path_bonus = 1.0 if any(token in chunk.path.lower() for token in query_tokens) else 0.0
        symbol_bonus = 1.0 if chunk.symbol and any(token in chunk.symbol.lower() for token in query_tokens) else 0.0
        return round(score + overlap + path_bonus + symbol_bonus, 4)


class HeuristicReranker:
    """Rerank lexical candidates with simple coverage heuristics."""

    def rerank(self, query: str, candidates: list[tuple[CodeChunk, float]]) -> list[tuple[CodeChunk, float]]:
        query_tokens = set(_tokenize(query))
        reranked: list[tuple[CodeChunk, float]] = []
        for chunk, score in candidates:
            chunk_tokens = set(_tokenize(chunk.content))
            coverage = len(query_tokens & chunk_tokens)
            density = coverage / max(math.sqrt(len(chunk_tokens) or 1), 1.0)
            reranked.append((chunk, round(score + density, 4)))
        return sorted(reranked, key=lambda item: item[1], reverse=True)


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]

