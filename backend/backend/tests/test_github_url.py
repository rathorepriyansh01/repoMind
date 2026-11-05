import pytest

from app.services.github_url import parse_repo_url


@pytest.mark.parametrize(
    "url, owner, repo",
    [
        ("https://github.com/tiangolo/fastapi", "tiangolo", "fastapi"),
        ("https://www.github.com/tiangolo/fastapi.git", "tiangolo", "fastapi"),
        ("https://github.com/tiangolo/fastapi/tree/main/docs", "tiangolo", "fastapi"),
        ("https://github.com/acme/demo/tree/feature/slash-branch/src", "acme", "demo"),
    ],
)
def test_valid_urls(url, owner, repo):
    parsed = parse_repo_url(url)
    assert parsed.owner == owner
    assert parsed.repo == repo
    assert parsed.normalized == f"{owner}/{repo}"


def test_encoded_and_nested_tree():
    parsed = parse_repo_url("https://github.com/acme/demo/tree/feature%2Fslash-branch")
    assert parsed.requested_ref == "feature/slash-branch"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://github.com/a/b",
        "http://github.com/a/b",
        "https://evil.com/a/b",
        "https://github.com/a",
        "https://github.com/bad owner/repo",
        "https://127.0.0.1/a/b",
        "https://github.com/user:pass@github.com/a/b",
        "https://github.com/settings/profile",
        "https://github.com/./..",
    ],
)
def test_invalid_urls(url):
    with pytest.raises(ValueError):
        parse_repo_url(url)
