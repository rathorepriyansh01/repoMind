import re
from pathlib import PurePosixPath

SECRET_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    "id_rsa",
    "id_dsa",
    "id_ed25519",
    "id_ecdsa",
    "credentials.json",
    "service-account.json",
    "secrets.yaml",
    "secrets.yml",
    "secrets.json",
}

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"), "[redacted-private-key]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted-aws-key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[redacted-github-token]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "[redacted-github-token]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[redacted-slack-token]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "[redacted-api-key]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "[redacted-google-key]"),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|secret|token|password|passwd|authorization)\b(\s*[:=]\s*)(['\"]?)[^\s'\"#]{8,}\3"
        ),
        r"\1\2\3[redacted]\3",
    ),
]


def redact_secrets(text: str) -> tuple[str, bool]:
    redacted = text
    changed = False
    for pattern, replacement in SECRET_PATTERNS:
        updated, count = pattern.subn(replacement, redacted)
        if count:
            redacted = updated
            changed = True
    return redacted, changed


def is_secret_filename(name: str) -> bool:
    lowered = name.lower()
    if lowered in SECRET_FILE_NAMES:
        return True
    if lowered.endswith(".pem") or lowered.endswith(".p12") or lowered.endswith(".key"):
        return True
    return False


def safe_repo_path(path: str) -> str:
    if not path or path.startswith("/") or path.startswith("\\"):
        raise ValueError("File path is invalid.")
    normalized = str(PurePosixPath(path.replace("\\", "/")))
    if normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise ValueError("File path is invalid.")
    if normalized in {".", ""}:
        raise ValueError("File path is invalid.")
    return normalized
