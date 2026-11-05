from __future__ import annotations

from typing import Any

from app.config import get_settings


def chunk_file(path: str, content: str, language: str, commit_sha: str) -> list[dict[str, Any]]:
    settings = get_settings()
    lines = content.splitlines()
    if not lines:
        return []
    max_lines = max(20, settings.chunk_lines)
    overlap = min(settings.chunk_overlap, max_lines // 3)
    chunks: list[dict[str, Any]] = []
    start = 0
    while start < len(lines):
        end = min(len(lines), start + max_lines)
        text = "\n".join(lines[start:end]).strip()
        if text:
            chunks.append({
                "file_path": path,
                "start_line": start + 1,
                "end_line": end,
                "content": text,
                "language": language,
                "commit_sha": commit_sha,
            })
        if end >= len(lines):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_files(files: list[dict[str, Any]], commit_sha: str) -> list[dict[str, Any]]:
    settings = get_settings()
    chunks: list[dict[str, Any]] = []
    for file in files:
        pieces = chunk_file(file["path"], file.get("content") or "", file.get("language") or "text", commit_sha)
        chunks.extend(pieces)
        if len(chunks) >= settings.max_chunks:
            return chunks[: settings.max_chunks]
    return chunks
