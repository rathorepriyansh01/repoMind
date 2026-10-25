from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db import db, dumps, loads
from app.security import safe_repo_path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def find_cached(full_name: str, commit_sha: str, embedding_model: str) -> dict[str, Any] | None:
    cursor = await db().execute(
        """
        SELECT * FROM repositories
        WHERE full_name = ? AND commit_sha = ? AND embedding_model = ?
        ORDER BY updated_at DESC LIMIT 1
        """,
        (full_name, commit_sha, embedding_model),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def save_repository(payload: dict[str, Any], report: dict[str, Any], embedding_model: str) -> str:
    facts = payload["facts"]
    repo_id = str(uuid.uuid4())
    conn = db()
    stamp = now()
    await conn.execute(
        """
        INSERT INTO repositories (
            id, owner, name, full_name, html_url, description, homepage, default_branch,
            commit_sha, language, languages_json, stars, forks, open_issues, license,
            github_created_at, github_updated_at, size, topics_json, visibility, archived,
            analysis_json, stats_json, tree_json, index_status, embedding_model,
            content_fingerprint, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            repo_id,
            facts["owner"],
            facts["name"],
            facts["full_name"],
            facts.get("html_url"),
            facts.get("description"),
            facts.get("homepage"),
            facts.get("default_branch"),
            payload["commit_sha"],
            facts.get("language"),
            dumps(facts.get("languages") or {}),
            facts.get("stars") or 0,
            facts.get("forks") or 0,
            facts.get("open_issues") or 0,
            facts.get("license"),
            facts.get("created_at"),
            facts.get("updated_at"),
            facts.get("size") or 0,
            dumps(facts.get("topics") or []),
            facts.get("visibility"),
            1 if facts.get("archived") else 0,
            dumps(report),
            dumps(payload.get("stats") or {}),
            dumps(payload.get("tree") or []),
            "indexed",
            embedding_model,
            payload["commit_sha"],
            stamp,
            stamp,
        ),
    )
    for file in payload.get("files") or []:
        await conn.execute(
            """
            INSERT INTO files (repository_id, path, sha, language, content, size, line_count, html_url, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo_id,
                file["path"],
                file.get("sha"),
                file.get("language"),
                file.get("content"),
                file.get("size") or 0,
                file.get("line_count") or 0,
                file.get("html_url"),
                file.get("content_hash"),
            ),
        )
    await conn.commit()
    return repo_id


async def list_repositories() -> list[dict[str, Any]]:
    cursor = await db().execute(
        """
        SELECT id, full_name, description, language, stars, commit_sha, updated_at, html_url, default_branch
        FROM repositories ORDER BY updated_at DESC LIMIT 50
        """
    )
    return [dict(row) for row in await cursor.fetchall()]


async def get_repository(repo_id: str) -> dict[str, Any] | None:
    cursor = await db().execute("SELECT * FROM repositories WHERE id = ?", (repo_id,))
    row = await cursor.fetchone()
    if not row:
        return None
    data = dict(row)
    data["analysis"] = loads(data.pop("analysis_json"), {})
    data["stats"] = loads(data.pop("stats_json"), {})
    data["tree"] = loads(data.pop("tree_json"), [])
    data["languages"] = loads(data.pop("languages_json"), {})
    data["topics"] = loads(data.pop("topics_json"), [])
    data["archived"] = bool(data.get("archived"))
    return data


async def get_file(repo_id: str, path: str) -> dict[str, Any] | None:
    safe = safe_repo_path(path)
    cursor = await db().execute(
        "SELECT path, language, content, size, line_count, html_url FROM files WHERE repository_id = ? AND path = ?",
        (repo_id, safe),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_files(repo_id: str) -> list[dict[str, Any]]:
    cursor = await db().execute(
        "SELECT path, language, size, line_count, html_url FROM files WHERE repository_id = ? ORDER BY path",
        (repo_id,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def create_job() -> str:
    job_id = str(uuid.uuid4())
    stamp = now()
    await db().execute(
        "INSERT INTO jobs (id, status, error, repository_id, progress, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, "queued", None, None, "Queued", stamp, stamp),
    )
    await db().commit()
    return job_id


async def update_job(job_id: str, **fields: Any) -> None:
    fields["updated_at"] = now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]
    await db().execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)
    await db().commit()


async def get_job(job_id: str) -> dict[str, Any] | None:
    cursor = await db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def create_chat(repo_id: str, title: str) -> dict[str, Any]:
    chat_id = str(uuid.uuid4())
    stamp = now()
    await db().execute(
        "INSERT INTO chats (id, repository_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (chat_id, repo_id, title[:120], stamp, stamp),
    )
    await db().commit()
    return {"id": chat_id, "repository_id": repo_id, "title": title[:120], "created_at": stamp, "updated_at": stamp}


async def list_chats(repo_id: str) -> list[dict[str, Any]]:
    cursor = await db().execute(
        "SELECT id, repository_id, title, created_at, updated_at FROM chats WHERE repository_id = ? ORDER BY updated_at DESC",
        (repo_id,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def get_chat(repo_id: str, chat_id: str) -> dict[str, Any] | None:
    cursor = await db().execute(
        "SELECT * FROM chats WHERE id = ? AND repository_id = ?",
        (chat_id, repo_id),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    chat = dict(row)
    messages = await db().execute(
        "SELECT id, role, content, citations_json, uncertainty, created_at FROM messages WHERE chat_id = ? ORDER BY created_at",
        (chat_id,),
    )
    chat["messages"] = [
        {
            "id": m["id"],
            "role": m["role"],
            "content": m["content"],
            "citations": loads(m["citations_json"], []),
            "uncertainty": m["uncertainty"],
            "created_at": m["created_at"],
        }
        for m in await messages.fetchall()
    ]
    return chat


async def delete_chat(repo_id: str, chat_id: str) -> bool:
    chat = await get_chat(repo_id, chat_id)
    if not chat:
        return False
    await db().execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    await db().execute("DELETE FROM chats WHERE id = ? AND repository_id = ?", (chat_id, repo_id))
    await db().commit()
    return True


async def add_message(chat_id: str, role: str, content: str, citations: list[dict[str, Any]] | None = None, uncertainty: str | None = None) -> str:
    message_id = str(uuid.uuid4())
    await db().execute(
        "INSERT INTO messages (id, chat_id, role, content, citations_json, uncertainty, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message_id, chat_id, role, content, dumps(citations or []), uncertainty, now()),
    )
    await db().execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now(), chat_id))
    await db().commit()
    return message_id


async def recent_messages(chat_id: str, limit: int) -> list[dict[str, Any]]:
    cursor = await db().execute(
        "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
        (chat_id, limit),
    )
    rows = [dict(row) for row in await cursor.fetchall()]
    rows.reverse()
    return rows
