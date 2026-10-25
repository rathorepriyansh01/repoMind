def test_end_to_end_smoke(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200

    started = client.post("/api/v1/analyze", json={"url": "https://github.com/acme/demo"})
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "succeeded"
    repo_id = job["repository_id"]

    analysis = client.get(f"/api/v1/repositories/{repo_id}").json()
    assert analysis["repository"]["full_name"] == "acme/demo"
    assert analysis["report"]["summary"]

    source = client.get(f"/api/v1/repositories/{repo_id}/files", params={"path": "app/main.py"}).json()
    assert "FastAPI" in source["content"]

    chat = client.post(
        f"/api/v1/repositories/{repo_id}/chat",
        json={"question": "Explain the health endpoint"},
    ).json()
    assert chat["citations"]
    assert any(c["path"] == "app/main.py" for c in chat["citations"])

    listed = client.get("/api/v1/repositories").json()["items"]
    assert any(item["id"] == repo_id for item in listed)
