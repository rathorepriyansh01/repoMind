import logging
import re
from typing import Any

SECRET_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        message = BEARER_PATTERN.sub("Bearer [redacted]", message)
        return SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=[redacted]", message)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def safe_error(exc: BaseException) -> str:
    return type(exc).__name__


def compact(value: Any, limit: int = 200) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"
