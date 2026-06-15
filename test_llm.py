import pytest
from unittest.mock import AsyncMock, patch
from llm import llm_complete


@pytest.mark.asyncio
async def test_llm_complete_success():
    mock_choice = AsyncMock()
    mock_choice.message = AsyncMock(content="test response")
    mock_response = AsyncMock()
    mock_response.choices = [mock_choice]

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("llm.get_client", return_value=mock_client):
        result = await llm_complete("test prompt")
        assert result == "test response"


@pytest.mark.asyncio
async def test_llm_complete_returns_none_on_error():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API error"))

    with patch("llm.get_client", return_value=mock_client):
        result = await llm_complete("test prompt")
        assert result is None
