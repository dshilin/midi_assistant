"""Client registry: each clients/<slug>/config.toml is one store."""
import os
import tomllib

CLIENTS_DIR = "clients"


def list_clients() -> list[str]:
    if not os.path.isdir(CLIENTS_DIR):
        return []
    return [
        d
        for d in os.listdir(CLIENTS_DIR)
        if os.path.isfile(os.path.join(CLIENTS_DIR, d, "config.toml"))
    ]


def get_client(slug: str) -> dict | None:
    path = os.path.join(CLIENTS_DIR, slug, "config.toml")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("slug", slug)
    return cfg


def require_client(slug: str) -> dict:
    cfg = get_client(slug)
    if cfg is None:
        raise ValueError(f"Unknown client slug: {slug}")
    return cfg


def get_db_path(slug: str) -> str:
    return os.path.join(CLIENTS_DIR, slug, "products.db")


def default_client_slug() -> str:
    """Первый настроенный клиент (конфиг-управляемый дефолт вместо хардкода бренда)."""
    clients = sorted(list_clients())
    if not clients:
        raise ValueError("no clients configured")
    return clients[0]
