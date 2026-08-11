from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import clients
from app.tg_bot import build_bots, get_telegram_token, handle_start, handle_text


class FakeBot:
    client_slug = "store"


def _make_client(root, slug, token="100:token"):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.toml").write_text(f'bot_token = "{token}"\n', encoding="utf-8")


def test_get_telegram_token_uses_client_config(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    _make_client(tmp_path, "cfg", token="123:cfg-token")

    assert get_telegram_token("cfg") == "123:cfg-token"


def test_get_telegram_token_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", "/nonexistent")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:env-token")

    assert get_telegram_token("midi") == "123:env-token"


def test_get_telegram_token_requires_value(monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", "/nonexistent")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr("app.tg_bot.load_dotenv", lambda: None)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_token("midi")


@pytest.mark.asyncio
async def test_handle_start_replies_with_greeting():
    message = SimpleNamespace(answer=AsyncMock())

    await handle_start(message)

    message.answer.assert_awaited_once()
    assert "Здравствуйте" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_handle_text_routes_by_bot_client(monkeypatch):
    message = SimpleNamespace(
        text="нужен светлый ламинат",
        from_user=SimpleNamespace(id=42),
        answer=AsyncMock(),
        bot=FakeBot(),
    )
    run_agent = AsyncMock(return_value=("Вот варианты", {"stage": "selection"}))
    monkeypatch.setattr("app.tg_bot.run_fsm_agent", run_agent)

    await handle_text(message)

    run_agent.assert_awaited_once_with("tg:store:42", "нужен светлый ламинат", client_slug="store")
    message.answer.assert_awaited_once_with("Вот варианты")


@pytest.mark.asyncio
async def test_handle_text_replies_to_non_text():
    message = SimpleNamespace(text=None, from_user=SimpleNamespace(id=42), answer=AsyncMock(), bot=FakeBot())

    await handle_text(message)

    message.answer.assert_awaited_once_with("Пока я понимаю только текстовые сообщения.")


def test_build_bots_returns_one_per_token(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    for i, slug in enumerate(("a", "b", "c"), start=100):
        _make_client(tmp_path, slug, token=f"{i}:{slug}-tok")

    bots = build_bots()

    assert {b.client_slug for b in bots} == {"a", "b", "c"}


def test_build_bots_raises_without_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="bot_token"):
        build_bots()
