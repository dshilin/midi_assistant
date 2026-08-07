# Клиент egger: скрейпер egger-laminate.ru — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить клиента `egger` (скрейпер egger-laminate.ru → catalog.csv + config.toml) в мультиклиентскую архитектуру без изменений ядра.

**Architecture:** Новый клиент = папка `clients/egger/` с `config.toml` и одноразовым скрейпером `scrape.py` вне ядра (как `clients/midi/`). Скрейпер читает разделы `/laminat` (пагинация 1..N), `/probkoviy-pol`, `/podlozhka`, извлекает название/цену/ссылку/артикул и пишет `catalog.csv` с шапкой `Артикул, Наименование, Цена, Ссылка`. Дальше загрузку делает существующий `python -m app.ingest egger`.

**Tech Stack:** Python 3, requests, BeautifulSoup, stdlib (re, csv, os, urllib.parse).

**Среда:** ветка `client-egger`, ворктри `.worktrees/client-egger` (репозиторий в `/home/claw/workspace/midi_assistant`).

---

### Task 1: config.toml клиента egger

**Files:**
- Create: `clients/egger/config.toml`

- [ ] **Step 1: Создать файл конфига**

`clients/egger/config.toml`:

```toml
name = "Egger"
slug = "egger"
bot_token = ""
site_url = "https://egger-laminate.ru"
```

- [ ] **Step 2: Проверить, что клиент виден в реестре**

Run: `python3 -c "from app import clients; print(clients.list_clients())"`
Expected: в списке есть `{'slug': 'egger', ...}`

- [ ] **Step 3: Commit**

```bash
git add clients/egger/config.toml
git commit -m "feat: конфиг клиента egger"
```

### Task 2: скрейпер clients/egger/scrape.py

**Files:**
- Create: `clients/egger/scrape.py`

- [ ] **Step 1: Написать скрейпер**

`clients/egger/scrape.py` (по образцу `clients/midi/scrape.py`):

```python
"""Одноразовый скрейпер каталога egger-laminate.ru -> clients/egger/catalog.csv.

Скрипт вне ядра: его можно править под изменение структуры сайта — на агента
это не влияет. Запуск: python3 clients/egger/scrape.py
"""
import csv
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://egger-laminate.ru"
OUT = os.path.join(os.path.dirname(__file__), "catalog.csv")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
ARTICLE_RE = re.compile(r"^([A-Z]{2,3}\d{3})\b")


def fetch(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def last_page(soup: BeautifulSoup) -> int:
    """Номер последней страницы из ссылки «Последняя» (пагинация /laminat)."""
    for a in soup.select("#navi a[href*='page=']"):
        if "Последняя" in a.get_text():
            m = re.search(r"/page=(\d+)", a.get("href", ""))
            if m:
                return int(m.group(1))
    return 1


def cards(soup: BeautifulSoup) -> list[dict]:
    out = []
    for a in soup.select("a[href*='/decor/']"):
        card = a.select_one(".cbt")
        if card is None:
            continue
        name = (card.select_one("h4") or a).get_text(strip=True)
        if not name:
            continue
        price = ""
        price_el = card.select_one(".bbcp")
        if price_el:
            spans = price_el.select("span")
            price = spans[0].get_text(strip=True) if spans else price_el.get_text(strip=True)
        m = ARTICLE_RE.match(name)
        out.append({
            "article": m.group(1) if m else "",
            "name": name,
            "price": price,
            "url": urljoin(BASE, a.get("href", "")),
        })
    return out


def scrape() -> list[dict]:
    products = []
    soup = fetch(BASE + "/laminat")
    products += cards(soup)
    for page in range(2, last_page(soup) + 1):
        products += cards(fetch(f"{BASE}/laminat/page={page}"))
    products += cards(fetch(BASE + "/probkoviy-pol"))
    products += cards(fetch(BASE + "/podlozhka"))
    return products


def main():
    products = scrape()
    print(f"Найдено: {len(products)}")
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Артикул", "Наименование", "Цена", "Ссылка"])
        for p in products:
            if p["name"]:
                w.writerow([p["article"], p["name"], p["price"], p["url"]])
    print(f"Каталог сохранён: {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Запустить скрейпер**

Run: `python3 clients/egger/scrape.py` (из корня ворктри, где стоит `requests`/`bs4`)
Expected: `Найдено: N` (N > 100), `Каталог сохранён: .../clients/egger/catalog.csv`

- [ ] **Step 3: Проверить выгрузку**

Run:
```bash
python3 - <<'EOF'
import csv
rows = list(csv.reader(open("clients/egger/catalog.csv", encoding="utf-8-sig")))
print(rows[0], len(rows) - 1)
print(rows[1])
print([r for r in rows[1:20] if r[0].startswith("EPC")][:1])
print([r for r in rows[1:20] if not r[0]][:1])
EOF
```
Expected: шапка `['Артикул', 'Наименование', 'Цена', 'Ссылка']`; в первой строке товар с артикулом `EPL...`; есть строки с артикулами `EPC...` (пробка) и с пустым артикулом (подложка); в каждой строке 4 колонки.

- [ ] **Step 4: Commit**

```bash
git add clients/egger/scrape.py clients/egger/catalog.csv
git commit -m "feat: скрейпер каталога egger-laminate.ru"
```

### Task 3: проверка ingest

**Files:**
- Test: `clients/egger/products.db` (создаётся при запуске; в git не добавляется)

- [ ] **Step 1: Загрузить каталог через ingest**

Run: `python3 -m app.ingest egger --no-parse`
Expected: `каталог egger: N товаров` (N совпадает с шагом 2 Task 2), `Загружено товаров: N`

- [ ] **Step 2: Проверить БД**

Run:
```bash
python3 -c "import sqlite3; c = sqlite3.connect('clients/egger/products.db'); print(c.execute('SELECT COUNT(*), COUNT(DISTINCT article) FROM products').fetchone())"
```
Expected: `(N, M)` где M близко к N (у подложки артикул пустой — строки с пустым артикулом в DISTINCT считаются одной).

- [ ] **Step 3: Полный цикл с GPT-парсером (по желанию, требует ключи Yandex)**

Run: `python3 -m app.ingest egger`
Expected: `Загружено товаров: N`, в логе `Total records in floor_covering_specs: ...`

- [ ] **Step 4: Commit**

```bash
git add -u clients/egger 2>/dev/null; git add clients/egger
git commit -m "chore: каталог egger (catalog.csv + БД клиента)"
```

> `products.db` клиента — по образцу midi (в `clients/midi/products.db`) — коммитится; при необходимости уточнить в .gitignore.
