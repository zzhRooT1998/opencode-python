from pathlib import Path

from opencode_py.retrieval.service import RetrievalService


def test_retrieval_service_returns_ranked_hits_with_path_and_lines(tmp_path: Path) -> None:
    (tmp_path / "cli.py").write_text(
        "\n".join(
            [
                "def session_list():",
                "    return ['abc']",
                "",
                "def chat():",
                "    return 'ok'",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "notes.md").write_text("The session list command shows history.", encoding="utf-8")

    service = RetrievalService(tmp_path)

    hits = service.retrieve("session list command", top_k=2)

    assert hits
    assert hits[0].path in {"cli.py", "notes.md"}
    assert hits[0].line_start >= 1
    assert hits[0].line_end >= hits[0].line_start
    assert hits[0].score > 0
    assert hits[0].reason


def test_retrieval_service_returns_empty_list_when_no_match(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    service = RetrievalService(tmp_path)

    hits = service.retrieve("database migration graph", top_k=3)

    assert hits == []

