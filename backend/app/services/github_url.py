from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from app.config import ALLOWED_GITHUB_WEB_HOSTS

OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


@dataclass(frozen=True)
class ParsedRepoURL:
    owner: str
    repo: str
    requested_ref: str | None = None
    requested_path: str | None = None
    normalized: str = ""


def _reject_private_host(hostname: str) -> None:
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise ValueError("Repository host is not allowed.")


def parse_repo_url(url: str) -> ParsedRepoURL:
    if not url or not isinstance(url, str):
        raise ValueError("Please enter a GitHub repository URL.")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise ValueError("Please enter a valid https://github.com/owner/repository URL.")
    if parsed.username or parsed.password:
        raise ValueError("Repository URL must not include credentials.")
    hostname = (parsed.hostname or "").lower()
    if hostname not in ALLOWED_GITHUB_WEB_HOSTS:
        raise ValueError("Only github.com repository URLs are supported.")
    _reject_private_host(hostname)
    parts = [unquote(p) for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError("Repository URL must include both owner and repository name.")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    if owner.lower() in {"orgs", "users", "settings", "marketplace", "topics", "explore", "login"}:
        raise ValueError("Repository URL must include both owner and repository name.")
    if not OWNER_RE.fullmatch(owner) or not REPO_RE.fullmatch(repo) or repo in {".", ".."}:
        raise ValueError("Repository URL contains an invalid owner or repository name.")
    requested_ref = None
    requested_path = None
    rest = parts[2:]
    if rest and rest[0] in {"tree", "blob", "raw", "commit"}:
        remainder = rest[1:]
        if remainder:
            requested_ref = "/".join(remainder)
    return ParsedRepoURL(
        owner=owner,
        repo=repo,
        requested_ref=requested_ref,
        requested_path=requested_path,
        normalized=f"{owner}/{repo}",
    )
