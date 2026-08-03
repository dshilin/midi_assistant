import os

import pytest

from app import clients


def _make_client(root: str, slug: str, bot_token: str = "") -> None:
    d = os.path.join(root, slug)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.toml"), "w", encoding="utf-8") as f:
        f.write(f'name = "{slug}"\n')
        f.write(f'bot_token = "{bot_token}"\n')


def test_list_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    _make_client(str(tmp_path), "midi")
    _make_client(str(tmp_path), "store2")
    (tmp_path / "broken").mkdir()

    assert clients.list_clients() == ["midi", "store2"]


def test_get_client_returns_config(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    _make_client(str(tmp_path), "midi", bot_token="t1")

    cfg = clients.get_client("midi")

    assert cfg["name"] == "midi"
    assert cfg["bot_token"] == "t1"
    assert cfg["slug"] == "midi"


def test_get_client_unknown_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))

    assert clients.get_client("nope") is None


def test_require_client_raises_for_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="nope"):
        clients.require_client("nope")


def test_get_db_path(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))

    assert clients.get_db_path("midi") == os.path.join(str(tmp_path), "midi", "products.db")
