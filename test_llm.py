import pytest
from unittest.mock import AsyncMock, patch
from llm import llm_complete


@pytest.mark.asyncio
async def test_llm_complete_openai_success():
    with patch("llm._llm_openai", new_callable=AsyncMock) as mock:
        mock.return_value = "test response"
        result = await llm_complete("test prompt")
        assert result == "test response"


@pytest.mark.asyncio
async def test_llm_complete_yandexgpt_success():
    with (
        patch("llm.LLM_PROVIDER", "yandexgpt"),
        patch("llm._llm_yandexgpt", new_callable=AsyncMock) as mock,
    ):
        mock.return_value = "test response"
        result = await llm_complete("test prompt")
        assert result == "test response"


@pytest.mark.asyncio
async def test_llm_complete_returns_none_on_error():
    with patch("llm._llm_openai", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("API error")
        result = await llm_complete("test prompt")
        assert result is None
