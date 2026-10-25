import base64
import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("LLM_BASE_URL", "")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("LLM_MODEL", "")
os.environ.setdefault("EMBEDDING_MODEL", "")
os.environ.setdefault("GITHUB_TOKEN", "")


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


README = "# Demo\nA tiny FastAPI demo used in tests.\n\n- Analyze repos\n"
MAIN_PY = """from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/items")
def items():
    return {"created": True}

if __name__ == "__main__":
    print("run")
"""
REQ = "fastapi>=0.115\nhttpx>=0.27\n"
PKG = json.dumps({"name": "demo-ui", "scripts": {"dev": "vite"}, "dependencies": {"react": "^18.0.0", "vite": "^6.0.0"}})
ENV_EXAMPLE = "LLM_API_KEY=\nGITHUB_TOKEN=\n"


def github_transport() -> httpx.MockTransport:
    blobs = {
        "sha-readme": README,
        "sha-main": MAIN_PY,
        "sha-req": REQ,
        "sha-pkg": PKG,
        "sha-env": ENV_EXAMPLE,
        "sha-secret": "SECRET_KEY=supersecretvalue123",
    }
    tree = {
        "sha": "commit-abc",
        "truncated": False,
        "tree": [
            {"path": "README.md", "type": "blob", "size": len(README), "sha": "sha-readme"},
            {"path": "app/main.py", "type": "blob", "size": len(MAIN_PY), "sha": "sha-main"},
            {"path": "requirements.txt", "type": "blob", "size": len(REQ), "sha": "sha-req"},
            {"path": "frontend/package.json", "type": "blob", "size": len(PKG), "sha": "sha-pkg"},
            {"path": ".env.example", "type": "blob", "size": len(ENV_EXAMPLE), "sha": "sha-env"},
            {"path": ".env", "type": "blob", "size": 40, "sha": "sha-secret"},
            {"path": "node_modules/pkg/index.js", "type": "blob", "size": 10, "sha": "sha-skip"},
            {"path": "binary.bin", "type": "blob", "size": 12, "sha": "sha-bin"},
            {"path": "huge.py", "type": "blob", "size": 9_000_000, "sha": "sha-huge"},
            {"path": "app", "type": "tree", "size": 0, "sha": "sha-dir"},
        ],
    }
    repo_meta = {
        "full_name": "acme/demo",
        "name": "demo",
        "description": "Demo repository for tests",
        "html_url": "https://github.com/acme/demo",
        "homepage": "https://example.com",
        "default_branch": "develop",
        "stargazers_count": 12,
        "forks_count": 3,
        "open_issues_count": 1,
        "language": "Python",
        "license": {"spdx_id": "MIT"},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-06-01T00:00:00Z",
        "size": 42,
        "topics": ["demo"],
        "visibility": "public",
        "private": False,
        "archived": False,
        "owner": {"login": "acme"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/repos/acme/demo":
            return httpx.Response(200, json=repo_meta)
        if path == "/repos/acme/missing":
            return httpx.Response(404, json={"message": "Not Found"})
        if path == "/repos/acme/private":
            private = dict(repo_meta)
            private["private"] = True
            private["full_name"] = "acme/private"
            return httpx.Response(200, json=private)
        if path == "/repos/acme/ratelimit":
            return httpx.Response(403, json={"message": "API rate limit exceeded"})
        if path == "/repos/acme/demo/languages":
            return httpx.Response(200, json={"Python": 800, "JavaScript": 200})
        if path == "/repos/acme/demo/readme":
            return httpx.Response(200, json={"path": "README.md", "encoding": "base64", "content": _b64(README), "html_url": "https://github.com/acme/demo/blob/develop/README.md"})
        if path.startswith("/repos/acme/noreadme"):
            if path.endswith("/noreadme"):
                meta = dict(repo_meta)
                meta["full_name"] = "acme/noreadme"
                meta["name"] = "noreadme"
                return httpx.Response(200, json=meta)
            if path.endswith("/readme"):
                return httpx.Response(404, json={"message": "Not Found"})
            if path.endswith("/languages"):
                return httpx.Response(200, json={"Python": 10})
            if "/commits/" in path:
                return httpx.Response(200, json={"sha": "commit-abc"})
            if "/git/trees/" in path:
                return httpx.Response(200, json={"sha": "commit-abc", "truncated": False, "tree": [
                    {"path": "app.py", "type": "blob", "size": 20, "sha": "sha-main"}
                ]})
            if "/git/blobs/sha-main" in path:
                return httpx.Response(200, json={"encoding": "base64", "content": _b64("print('hi')\n")})
        if "/commits/" in path:
            ref = path.split("/commits/")[-1]
            if ref in {"develop", "commit-abc", "feature/slash-branch"}:
                return httpx.Response(200, json={"sha": "commit-abc"})
            return httpx.Response(404, json={"message": "Not Found"})
        if "/git/trees/" in path:
            truncated = path.endswith("truncated-ref")
            payload = dict(tree)
            payload["truncated"] = truncated
            return httpx.Response(200, json=payload)
        if "/git/blobs/" in path:
            sha = path.split("/git/blobs/")[-1]
            if sha not in blobs:
                return httpx.Response(404, json={"message": "Not Found"})
            return httpx.Response(200, json={"encoding": "base64", "content": _b64(blobs[sha])})
        if "/contents/" in path:
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"message": "Not Found"})

    return httpx.MockTransport(handler)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "repomind.db"))
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("MAX_FILE_BYTES", "120000")
    from app.config import get_settings
    get_settings.cache_clear()

    transport = github_transport()
    real_client = httpx.AsyncClient

    def wrapped(*args, **kwargs):
        kwargs["transport"] = transport
        kwargs.setdefault("base_url", "https://api.github.com")
        return real_client(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", wrapped)

    async def no_sleep(_delay, *_args, **_kwargs):
        return None

    monkeypatch.setattr("app.services.github_client.asyncio.sleep", no_sleep)
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
