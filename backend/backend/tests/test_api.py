def wait_job(client, job_id):
    for _ in range(20):
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        if data["status"] in {"succeeded", "failed"}:
            return data
    raise AssertionError("job did not finish")


def analyze_ok(client, url="https://github.com/acme/demo"):
    response = client.post("/api/v1/analyze", json={"url": url})
    assert response.status_code == 200
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "succeeded", job
    return job["repository_id"]


def test_health_and_ready(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["database"] is True
    assert body["llm_configured"] is False


def test_invalid_repository_url(client):
    response = client.post("/api/v1/analyze", json={"url": "https://evil.example/a/b"})
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "github.com" in job["error"].lower()


def test_missing_repository(client):
    response = client.post("/api/v1/analyze", json={"url": "https://github.com/acme/missing"})
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "not found" in job["error"].lower()


def test_rate_limit_error(client):
    response = client.post("/api/v1/analyze", json={"url": "https://github.com/acme/ratelimit"})
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "rate limit" in job["error"].lower()


def test_private_repository_rejected(client):
    response = client.post("/api/v1/analyze", json={"url": "https://github.com/acme/private"})
    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "failed"
    assert "public" in job["error"].lower()


def test_analyze_success_and_file_explorer(client):
    repo_id = analyze_ok(client)
    detail = client.get(f"/api/v1/repositories/{repo_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["repository"]["full_name"] == "acme/demo"
    assert body["repository"]["default_branch"] == "develop"
    assert body["repository"]["source"] == "github_api"
    assert body["report"]["mode"] == "heuristic"
    paths = {f["path"] for f in body["files"]}
    assert "app/main.py" in paths
    assert ".env" not in paths
    assert "node_modules/pkg/index.js" not in paths
    assert "huge.py" not in paths
    tree = client.get(f"/api/v1/repositories/{repo_id}/tree")
    assert "app/main.py" in tree.json()["tree"]
    file = client.get(f"/api/v1/repositories/{repo_id}/files", params={"path": "app/main.py"})
    assert file.status_code == 200
    assert "FastAPI" in file.json()["content"]
    assert "supersecretvalue123" not in file.json()["content"]


def test_path_traversal_rejected(client):
    repo_id = analyze_ok(client)
    response = client.get(f"/api/v1/repositories/{repo_id}/files", params={"path": "../.env"})
    assert response.status_code == 400


def test_missing_readme(client):
    repo_id = analyze_ok(client, "https://github.com/acme/noreadme")
    body = client.get(f"/api/v1/repositories/{repo_id}").json()
    assert any("README" in item for item in body["report"]["limitations"])


def test_index_reuse(client):
    first = analyze_ok(client)
    second = analyze_ok(client)
    assert first == second


def test_chat_fallback_and_sessions(client):
    repo_id = analyze_ok(client)
    response = client.post(
        f"/api/v1/repositories/{repo_id}/chat",
        json={"question": "Where is the health endpoint defined?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fallback"
    assert payload["citations"]
    assert payload["citations"][0]["path"] == "app/main.py"
    chat_id = payload["chat_id"]
    follow = client.post(
        f"/api/v1/repositories/{repo_id}/chat",
        json={"question": "What dependencies are declared?", "chat_id": chat_id},
    )
    assert follow.status_code == 200
    chats = client.get(f"/api/v1/repositories/{repo_id}/chats").json()["items"]
    assert any(item["id"] == chat_id for item in chats)
    detail = client.get(f"/api/v1/repositories/{repo_id}/chats/{chat_id}")
    assert len(detail.json()["messages"]) >= 4
    deleted = client.delete(f"/api/v1/repositories/{repo_id}/chats/{chat_id}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/v1/repositories/{repo_id}/chats/{chat_id}")
    assert missing.status_code == 404


def test_chat_isolation_between_repositories(client):
    demo = analyze_ok(client)
    other = analyze_ok(client, "https://github.com/acme/noreadme")
    leaked = client.get(f"/api/v1/repositories/{other}/files", params={"path": "frontend/package.json"})
    assert leaked.status_code == 404
    present = client.get(f"/api/v1/repositories/{demo}/files", params={"path": "frontend/package.json"})
    assert present.status_code == 200


def test_cors_headers(client):
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
