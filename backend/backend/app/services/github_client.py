from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import random
from typing import Any

import httpx

from app.config import get_settings
from app.security import is_secret_filename, redact_secrets, safe_repo_path
from app.services.github_url import ParsedRepoURL

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".go", ".rs",
    ".cpp", ".cc", ".c", ".h", ".hpp", ".cs", ".php", ".rb", ".swift", ".kt",
    ".sql", ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".md",
    ".txt", ".sh", ".bash", ".bat", ".ps1", ".xml", ".ini", ".cfg", ".conf",
    ".gradle", ".properties", ".env.example", ".gitignore", ".dockerignore",
    ".tf", ".prisma", ".graphql", ".vue", ".svelte",
}
SKIP_PARTS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__",
    ".next", ".nuxt", "coverage", ".cache", "vendor", "target", "out",
    "bower_components", ".terraform", "Pods",
}
SKIP_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "composer.lock", "cargo.lock",
}
IMPORTANT_NAMES = {
    "readme.md", "readme.rst", "readme.txt", "requirements.txt", "pyproject.toml",
    "package.json", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml", "main.py", "app.py", "index.js", "index.ts",
    "vite.config.js", "vite.config.ts", "manage.py", "go.mod", "cargo.toml",
    "pom.xml", "build.gradle", "gemfile", ".env.example", "makefile",
    "tsconfig.json", "next.config.js", "nuxt.config.ts", "prisma/schema.prisma",
}
LANGUAGE_BY_EXT = {
    "py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript",
    "tsx": "typescript", "go": "go", "rs": "rust", "java": "java", "rb": "ruby",
    "php": "php", "cs": "csharp", "kt": "kotlin", "swift": "swift", "sql": "sql",
    "md": "markdown", "yml": "yaml", "yaml": "yaml", "json": "json", "toml": "toml",
    "html": "html", "css": "css", "sh": "shell",
}


class GitHubError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "RepoMind-AI",
    }
    if settings.github_token.strip():
        headers["Authorization"] = f"Bearer {settings.github_token.strip()}"
    return headers


def _timeout() -> httpx.Timeout:
    settings = get_settings()
    return httpx.Timeout(settings.request_timeout_seconds, connect=settings.connect_timeout_seconds)


async def github_request(client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            last_error = exc
            await asyncio.sleep((2 ** attempt) * 0.25 + random.random() * 0.2)
            continue
        except httpx.HTTPError as exc:
            last_error = exc
            await asyncio.sleep((2 ** attempt) * 0.25 + random.random() * 0.2)
            continue
        if response.status_code in {403, 429}:
            message = response.text.lower()
            if "rate limit" in message or response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt) + random.random()
                wait = min(wait, 8.0)
                await asyncio.sleep(wait)
                last_error = GitHubError(
                    "GitHub rate limit reached. Try again later or configure GITHUB_TOKEN.",
                    429,
                )
                continue
            if response.status_code == 403:
                raise GitHubError("GitHub denied access to this repository.", 403)
        if response.status_code >= 500:
            await asyncio.sleep((2 ** attempt) * 0.3 + random.random() * 0.2)
            last_error = GitHubError("GitHub is temporarily unavailable.", 502)
            continue
        return response
    if isinstance(last_error, GitHubError):
        raise last_error
    raise GitHubError("Could not reach GitHub. Check your network connection and try again.", 502)


def _should_skip_path(path: str) -> bool:
    parts = path.split("/")
    if any(part in SKIP_PARTS for part in parts):
        return True
    name = parts[-1]
    if is_secret_filename(name):
        return True
    if name.lower() in SKIP_NAMES:
        return True
    return False


def _is_supported_file(path: str) -> bool:
    name = path.split("/")[-1].lower()
    if name in IMPORTANT_NAMES or name.endswith(".env.example"):
        return True
    if name in {"dockerfile", "makefile", "gemfile", "procfile"}:
        return True
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if name.startswith("dockerfile"):
        return True
    return ext in TEXT_EXTENSIONS


def language_for_path(path: str) -> str:
    name = path.split("/")[-1].lower()
    if "." not in name:
        return "text"
    ext = name.rsplit(".", 1)[-1]
    return LANGUAGE_BY_EXT.get(ext, ext)


class GitHubClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.base = get_settings().github_api_base

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> tuple[httpx.Response, Any]:
        url = f"{self.base}{path}"
        response = await github_request(self.client, "GET", url, params=params)
        if response.status_code == 204:
            return response, None
        try:
            return response, response.json()
        except ValueError as exc:
            raise GitHubError("GitHub returned an unreadable response.", 502) from exc

    async def fetch_repository(self, parsed: ParsedRepoURL) -> dict[str, Any]:
        response, meta = await self.get_json(f"/repos/{parsed.owner}/{parsed.repo}")
        if response.status_code == 404:
            raise GitHubError("Repository not found or not publicly accessible.", 404)
        if response.status_code == 403:
            raise GitHubError("GitHub denied access to this repository.", 403)
        if response.status_code >= 400:
            raise GitHubError("Could not load repository metadata from GitHub.", 502)
        if meta.get("private"):
            raise GitHubError("RepoMind analyzes public repositories only.", 400)
        if meta.get("size") == 0:
            raise GitHubError("This repository appears to be empty.", 400)
        return meta

    async def fetch_languages(self, owner: str, repo: str) -> dict[str, int]:
        response, data = await self.get_json(f"/repos/{owner}/{repo}/languages")
        if response.status_code != 200 or not isinstance(data, dict):
            return {}
        return {str(k): int(v) for k, v in data.items() if isinstance(v, int)}

    async def fetch_readme(self, owner: str, repo: str) -> dict[str, Any] | None:
        response, data = await self.get_json(f"/repos/{owner}/{repo}/readme")
        if response.status_code == 404:
            return None
        if response.status_code != 200 or not isinstance(data, dict):
            return None
        content = _decode_content(data)
        if content is None:
            return None
        redacted, _ = redact_secrets(content)
        return {"path": data.get("path") or "README.md", "content": redacted, "html_url": data.get("html_url")}

    async def resolve_ref(self, owner: str, repo: str, default_branch: str, requested_ref: str | None) -> str:
        if not requested_ref:
            return default_branch
        parts = requested_ref.split("/")
        for length in range(len(parts), 0, -1):
            candidate = "/".join(parts[:length])
            response, data = await self.get_json(f"/repos/{owner}/{repo}/commits/{candidate}")
            if response.status_code == 200 and isinstance(data, dict):
                return candidate
        return default_branch

    async def fetch_commit_sha(self, owner: str, repo: str, ref: str) -> str:
        response, data = await self.get_json(f"/repos/{owner}/{repo}/commits/{ref}")
        if response.status_code != 200 or not isinstance(data, dict):
            raise GitHubError("Could not resolve the repository default branch.", 502)
        sha = data.get("sha")
        if not sha:
            raise GitHubError("Could not resolve the repository commit.", 502)
        return sha

    async def fetch_tree(self, owner: str, repo: str, ref: str) -> tuple[list[dict[str, Any]], bool, str]:
        response, data = await self.get_json(f"/repos/{owner}/{repo}/git/trees/{ref}", params={"recursive": "1"})
        if response.status_code != 200 or not isinstance(data, dict):
            raise GitHubError("Could not load the repository file tree.", 502)
        tree = data.get("tree") or []
        truncated = bool(data.get("truncated"))
        sha = data.get("sha") or ref
        settings = get_settings()
        if truncated:
            extra = await self._expand_truncated_tree(owner, repo, ref)
            seen = {item.get("path") for item in tree}
            for item in extra:
                if item.get("path") not in seen:
                    tree.append(item)
                    seen.add(item.get("path"))
        if len(tree) > settings.max_tree_items:
            tree = tree[: settings.max_tree_items]
            truncated = True
        return tree, truncated, sha

    async def _expand_truncated_tree(self, owner: str, repo: str, ref: str) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        queue = [""]
        seen_dirs = {""}
        settings = get_settings()
        while queue and len(collected) < settings.max_tree_items:
            prefix = queue.pop(0)
            path = f"/repos/{owner}/{repo}/contents/{prefix}" if prefix else f"/repos/{owner}/{repo}/contents"
            response, data = await self.get_json(path, params={"ref": ref})
            if response.status_code != 200 or not isinstance(data, list):
                continue
            for item in data:
                item_path = item.get("path") or ""
                if item.get("type") == "dir":
                    if item_path not in seen_dirs and not _should_skip_path(item_path):
                        seen_dirs.add(item_path)
                        queue.append(item_path)
                    collected.append({"path": item_path, "type": "tree", "size": 0, "sha": item.get("sha")})
                elif item.get("type") == "file":
                    collected.append(
                        {"path": item_path, "type": "blob", "size": item.get("size") or 0, "sha": item.get("sha")}
                    )
        return collected

    async def fetch_files(self, owner: str, repo: str, ref: str, tree: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        settings = get_settings()
        eligible = []
        skipped_secret = 0
        skipped_binary = 0
        skipped_large = 0
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path") or ""
            try:
                safe_repo_path(path)
            except ValueError:
                continue
            if _should_skip_path(path):
                if is_secret_filename(path.split("/")[-1]):
                    skipped_secret += 1
                continue
            if not _is_supported_file(path):
                skipped_binary += 1
                continue
            size = int(item.get("size") or 0)
            if size > settings.max_file_bytes:
                skipped_large += 1
                continue
            eligible.append(item)
        eligible.sort(
            key=lambda item: (
                0 if item.get("path", "").split("/")[-1].lower() in IMPORTANT_NAMES else 1,
                item.get("path", "").count("/"),
                item.get("path", "").lower(),
            )
        )
        skipped_cap = max(0, len(eligible) - settings.max_files)
        eligible = eligible[: settings.max_files]
        semaphore = asyncio.Semaphore(settings.github_concurrency)
        files: list[dict[str, Any]] = []
        total_chars = 0

        async def load_one(item: dict[str, Any]) -> dict[str, Any] | None:
            path = item["path"]
            sha = item.get("sha")
            async with semaphore:
                if sha:
                    response, data = await self.get_json(f"/repos/{owner}/{repo}/git/blobs/{sha}")
                else:
                    response, data = await self.get_json(
                        f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref}
                    )
                if response.status_code != 200 or not isinstance(data, dict):
                    return None
                content = _decode_content(data)
                if content is None:
                    return None
                content, _ = redact_secrets(content)
                return {
                    "path": path,
                    "sha": sha or "",
                    "size": item.get("size") or len(content.encode("utf-8", errors="replace")),
                    "content": content,
                    "line_count": content.count("\n") + 1 if content else 0,
                    "html_url": f"https://github.com/{owner}/{repo}/blob/{ref}/{path}",
                    "language": language_for_path(path),
                    "content_hash": hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest(),
                }

        loaded = await asyncio.gather(*(load_one(item) for item in eligible), return_exceptions=True)
        for result in loaded:
            if isinstance(result, Exception) or result is None:
                continue
            remaining = settings.max_total_chars - total_chars
            if remaining <= 0:
                skipped_cap += 1
                continue
            content = result["content"]
            if len(content) > remaining:
                content = content[:remaining]
                result["content"] = content
                result["line_count"] = content.count("\n") + 1
            if not content.strip():
                continue
            files.append(result)
            total_chars += len(content)
        stats = {
            "tree_items": len(tree),
            "analyzed_files": len(files),
            "skipped_due_to_file_cap": skipped_cap,
            "skipped_secrets": skipped_secret,
            "skipped_unsupported": skipped_binary,
            "skipped_large": skipped_large,
            "total_characters": total_chars,
        }
        return files, stats


def _decode_content(data: dict[str, Any]) -> str | None:
    encoding = data.get("encoding")
    content = data.get("content")
    if encoding == "base64" and isinstance(content, str):
        try:
            raw = base64.b64decode(content)
        except (ValueError, TypeError):
            return None
        if b"\x00" in raw[:1024]:
            return None
        return raw.decode("utf-8", errors="replace")
    if isinstance(content, str) and encoding in {None, "utf-8"}:
        return content
    return None


async def collect_repository(parsed: ParsedRepoURL) -> dict[str, Any]:
    settings = get_settings()
    timeout = _timeout()
    async with httpx.AsyncClient(headers=_headers(), timeout=timeout, follow_redirects=False) as client:
        gh = GitHubClient(client)
        meta = await gh.fetch_repository(parsed)
        owner = meta.get("owner", {}).get("login") or parsed.owner
        repo = meta.get("name") or parsed.repo
        default_branch = meta.get("default_branch") or "main"
        branch = await gh.resolve_ref(owner, repo, default_branch, parsed.requested_ref)
        commit_sha = await gh.fetch_commit_sha(owner, repo, branch)
        languages = await gh.fetch_languages(owner, repo)
        readme = await gh.fetch_readme(owner, repo)
        tree, truncated, tree_sha = await gh.fetch_tree(owner, repo, commit_sha)
        files, stats = await gh.fetch_files(owner, repo, branch, tree)
        if readme and not any(f["path"].lower() == readme["path"].lower() for f in files):
            files.insert(0, {
                "path": readme["path"],
                "sha": "",
                "size": len(readme["content"]),
                "content": readme["content"],
                "line_count": readme["content"].count("\n") + 1,
                "html_url": readme.get("html_url"),
                "language": "markdown",
                "content_hash": hashlib.sha256(readme["content"].encode()).hexdigest(),
            })
            stats["analyzed_files"] = len(files)
        license_info = meta.get("license") or {}
        facts = {
            "owner": owner,
            "name": repo,
            "full_name": meta.get("full_name") or f"{owner}/{repo}",
            "description": meta.get("description"),
            "homepage": meta.get("homepage"),
            "html_url": meta.get("html_url"),
            "default_branch": default_branch,
            "analyzed_branch": branch,
            "stars": meta.get("stargazers_count", 0),
            "forks": meta.get("forks_count", 0),
            "open_issues": meta.get("open_issues_count", 0),
            "license": license_info.get("spdx_id") if isinstance(license_info, dict) else None,
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
            "size": meta.get("size"),
            "topics": meta.get("topics") or [],
            "visibility": meta.get("visibility") or "public",
            "archived": bool(meta.get("archived")),
            "language": meta.get("language"),
            "languages": languages,
            "source": "github_api",
        }
        tree_paths = [item.get("path", "") for item in tree if item.get("path")]
        stats.update({
            "tree_truncated": truncated,
            "tree_sha": tree_sha,
            "extension_counts": _extension_counts(files),
            "limits": {
                "max_files": settings.max_files,
                "max_file_bytes": settings.max_file_bytes,
                "max_total_chars": settings.max_total_chars,
            },
        })
        if meta.get("archived"):
            stats["warnings"] = ["This repository is archived on GitHub."]
        return {
            "facts": facts,
            "commit_sha": commit_sha,
            "readme": readme,
            "files": files,
            "tree": tree_paths,
            "stats": stats,
        }


def _extension_counts(files: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for file in files:
        ext = file["path"].rsplit(".", 1)[-1].lower() if "." in file["path"] else "other"
        counts[ext] = counts.get(ext, 0) + 1
    return counts
