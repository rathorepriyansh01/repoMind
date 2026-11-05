import httpx
import pytest

from app.services.llm import LLMProvider, parse_json_object


def test_parse_json_from_fenced_block():
    raw = "```json\n{\"summary\": \"ok\"}\n```"
    assert parse_json_object(raw)["summary"] == "ok"


@pytest.mark.asyncio
async def test_llm_timeout_returns_none(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    from app.config import get_settings
    get_settings.cache_clear()

    class Boom:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("app.services.llm.httpx.AsyncClient", Boom)
    provider = LLMProvider()
    assert await provider.complete([{"role": "user", "content": "hi"}]) is None
    get_settings.cache_clear()
