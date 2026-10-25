from app.services.analyzer import analyze_repository_evidence


def test_analyzer_extracts_fastapi_routes_and_deps():
    payload = {
        "facts": {
            "full_name": "acme/demo",
            "language": "Python",
            "languages": {"Python": 10},
            "description": "Demo app",
        },
        "files": [
            {
                "path": "app/main.py",
                "content": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health():\n    return 1\n",
                "line_count": 5,
                "html_url": "https://github.com/acme/demo/blob/main/app/main.py",
            },
            {
                "path": "requirements.txt",
                "content": "fastapi>=0.115\n",
                "line_count": 1,
                "html_url": "x",
            },
        ],
        "tree": ["app/main.py", "requirements.txt", "tests/test_app.py"],
        "readme": {"path": "README.md", "content": "# Demo\nThis project analyzes github repositories.\n"},
        "stats": {},
    }
    report = analyze_repository_evidence(payload)
    assert report["mode"] == "heuristic"
    assert any(t["name"] == "FastAPI" for t in report["technologies"])
    assert any(e["path"] == "/health" for e in report["api_endpoints"])
    assert report["dependencies"]["ecosystems"][0]["name"] == "python"
    assert report["testing"]["test_file_count_in_tree"] >= 1
    assert "not executed" in report["quality"]["disclaimer"].lower()
