from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL,
    html_url TEXT,
    description TEXT,
    homepage TEXT,
    default_branch TEXT,
    commit_sha TEXT,
    language TEXT,
    languages_json TEXT,
    stars INTEGER,
    forks INTEGER,
    open_issues INTEGER,
    license TEXT,
    github_created_at TEXT,
    github_updated_at TEXT,
    size INTEGER,
    topics_json TEXT,
    visibility TEXT,
    archived INTEGER,
    analysis_json TEXT,
    stats_json TEXT,
    tree_json TEXT,
    index_status TEXT,
    embedding_model TEXT,
    content_fingerprint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id TEXT NOT NULL,
    path TEXT NOT NULL,
    sha TEXT,
    language TEXT,
    content TEXT,
    size INTEGER,
    line_count INTEGER,
    html_url TEXT,
    content_hash TEXT,
    UNIQUE(repository_id, path)
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT,
    language TEXT,
    embedding_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    file_path,
    chunk_id UNINDEXED
);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT,
    uncertainty TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    error TEXT,
    repository_id TEXT,
    progress TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_repos_full_name ON repositories(full_name, commit_sha);
CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repository_id);
CREATE INDEX IF NOT EXISTS idx_chunks_repo ON chunks(repository_id);
CREATE INDEX IF NOT EXISTS idx_chats_repo ON chats(repository_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
"""

_connection: aiosqlite.Connection | None = None


def _db_path() -> Path:
    path = Path(get_settings().database_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def init_db() -> None:
    global _connection
    db_file = _db_path()
    _connection = await aiosqlite.connect(db_file.as_posix())
    _connection.row_factory = aiosqlite.Row
    await _connection.execute("PRAGMA foreign_keys = ON")
    await _connection.executescript(SCHEMA)
    await _connection.commit()


async def close_db() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None


def db() -> aiosqlite.Connection:
    if _connection is None:
        raise RuntimeError("Database is not initialized.")
    return _connection


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
