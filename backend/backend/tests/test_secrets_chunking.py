from app.security import redact_secrets, safe_repo_path
from app.services.chunking import chunk_file
import pytest


def test_redact_api_key_and_pem():
    text = "api_key=sk-abcdefghijklmnopqrstuvwxyz123456\n-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"
    redacted, changed = redact_secrets(text)
    assert changed
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in redacted
    assert "[redacted" in redacted


def test_path_traversal_rejected():
    with pytest.raises(ValueError):
        safe_repo_path("../secrets.txt")
    with pytest.raises(ValueError):
        safe_repo_path("/etc/passwd")
    assert safe_repo_path("app/main.py") == "app/main.py"


def test_chunk_preserves_line_ranges():
    content = "\n".join(f"line-{i}" for i in range(1, 101))
    chunks = chunk_file("demo.py", content, "python", "abc")
    assert chunks
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["file_path"] == "demo.py"
    assert chunks[-1]["end_line"] == 100
    combined_lines = sum(c["end_line"] - c["start_line"] + 1 for c in chunks)
    assert combined_lines >= 100
