import pytest

from app.tg_bot import get_telegram_token


def test_get_telegram_token_returns_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")

    assert get_telegram_token() == "123:abc"


def test_get_telegram_token_requires_value(monkeypatch):
    monkeypatch.setattr("app.tg_bot.load_dotenv", lambda: None)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_token()
