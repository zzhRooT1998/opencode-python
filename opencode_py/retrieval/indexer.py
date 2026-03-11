"""Repository indexing and chunking for lightweight code retrieval."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CodeChunk:
    """One retrievable chunk of repository content."""

    path: str
    line_start: int
    line_end: int
    content: str
    language: str
    symbol: str | None = None


class RepositoryIndexer:
    """Build a lightweight chunk index from repository files."""

    DEFAULT_PATTERNS = {".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml"}
    SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"}

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def build(self) -> list[CodeChunk]:
        """Scan the workspace and return indexed chunks."""

        chunks: list[CodeChunk] = []
        for path in self.workspace_root.rglob("*"):
            if not path.is_file() or self._should_skip(path):
                continue
            if path.suffix.lower() not in self.DEFAULT_PATTERNS:
                continue
            chunks.extend(self._chunks_for_file(path))
        return chunks

    def _chunks_for_file(self, path: Path) -> list[CodeChunk]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return []

        if path.suffix.lower() == ".py":
            python_chunks = self._python_chunks(path, text)
            if python_chunks:
                return python_chunks
        return self._text_chunks(path, text)

    def _python_chunks(self, path: Path, text: str) -> list[CodeChunk]:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return self._text_chunks(path, text)

        lines = text.splitlines()
        chunks: list[CodeChunk] = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            snippet = "\n".join(lines[start - 1 : end])
            chunks.append(
                CodeChunk(
                    path=str(path.relative_to(self.workspace_root)),
                    line_start=start,
                    line_end=end,
                    content=snippet,
                    language="python",
                    symbol=node.name,
                )
            )

        if chunks:
            return chunks
        return self._text_chunks(path, text)

    def _text_chunks(self, path: Path, text: str, lines_per_chunk: int = 30) -> list[CodeChunk]:
        lines = text.splitlines()
        chunks: list[CodeChunk] = []
        if not lines:
            return chunks

        for index in range(0, len(lines), lines_per_chunk):
            start = index + 1
            end = min(index + lines_per_chunk, len(lines))
            snippet = "\n".join(lines[index:end])
            chunks.append(
                CodeChunk(
                    path=str(path.relative_to(self.workspace_root)),
                    line_start=start,
                    line_end=end,
                    content=snippet,
                    language=_infer_language(path),
                )
            )
        return chunks

    def _should_skip(self, path: Path) -> bool:
        return any(part in self.SKIP_PARTS for part in path.parts)


def _infer_language(path: Path) -> str:
    if path.suffix.lower() == ".py":
        return "python"
    if path.suffix.lower() == ".md":
        return "markdown"
    return "text"

