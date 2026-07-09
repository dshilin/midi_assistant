from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.tg_bot import get_telegram_token, handle_start, handle_text


def test_get_telegram_token_returns_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")

    assert get_telegram_token() == "123:abc"


def test_get_telegram_token_requires_value(monkeypatch):
    monkeypatch.setattr("app.tg_bot.load_dotenv", lambda: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_token()


@pytest.mark.asyncio
async def test_handle_start_replies_with_greeting():
    message = SimpleNamespace(answer=AsyncMock())

    await handle_start(message)

    message.answer.assert_awaited_once()
    assert "Здравствуйте" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_handle_text_calls_fsm_agent(monkeypatch):
    message = SimpleNamespace(
        text="нужен светлый ламинат",
        from_user=SimpleNamespace(id=42),
        answer=AsyncMock(),
    )
    run_agent = AsyncMock(return_value=("Вот варианты", {"stage": "selection"}))
    monkeypatch.setattr("app.tg_bot.run_fsm_agent", run_agent)

    await handle_text(message)

    run_agent.assert_awaited_once_with("tg:42", "нужен светлый ламинат")
    message.answer.assert_awaited_once_with("Вот варианты")


@pytest.mark.asyncio
async def test_handle_text_replies_to_non_text():
    message = SimpleNamespace(text=None, from_user=SimpleNamespace(id=42), answer=AsyncMock())

    await handle_text(message)

    message.answer.assert_awaited_once_with("Пока я понимаю только текстовые сообщения.")
