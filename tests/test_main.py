from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import clients
from app.main import app


def _reg(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    for slug in ("midi", "store"):
        d = tmp_path / slug
        d.mkdir()
        (d / "config.toml").write_text(f'name = "{slug}"\n', encoding="utf-8")


def test_legacy_root(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)

    r = TestClient(app).get("/")

    assert r.status_code == 200


def test_site_index_unknown_client_404(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)

    assert TestClient(app).get("/missing").status_code == 404


def test_site_index_serves_html(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)

    r = TestClient(app).get("/midi")

    assert r.status_code == 200


def test_legacy_chat_routes_to_midi(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    with patch("app.main.run_fsm_agent", new_callable=AsyncMock) as agent:
        agent.return_value = ("ответ", {"stage": "discovery"})
        r = TestClient(app).post("/chat", json={"user_id": "u1", "message": "привет"})

    assert r.status_code == 200
    agent.assert_awaited_once_with("web:midi:u1", "привет", client_slug="midi")


def test_site_chat_routes_by_slug(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    with patch("app.main.run_fsm_agent", new_callable=AsyncMock) as agent:
        agent.return_value = ("ответ", {"stage": "selection"})
        r = TestClient(app).post("/store/chat", json={"user_id": "u2", "message": "хочу"})

    assert r.status_code == 200
    agent.assert_awaited_once_with("web:store:u2", "хочу", client_slug="store")


def test_site_chat_unknown_client_404(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    with patch("app.main.run_fsm_agent", new_callable=AsyncMock) as agent:
        r = TestClient(app).post("/missing/chat", json={"user_id": "u3", "message": "привет"})

    assert r.status_code == 404
    agent.assert_not_called()
