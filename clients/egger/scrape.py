"""Одноразовый скрейпер каталога egger-laminate.ru -> clients/egger/catalog.csv.

Скрипт вне ядра: его можно править под изменение структуры сайта — на агента
это не влияет. Запуск: python3 clients/egger/scrape.py
"""
import csv
import os
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://egger-laminate.ru"
OUT = os.path.join(os.path.dirname(__file__), "catalog.csv")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
ARTICLE_RE = re.compile(r"^([A-Z]{2,3}\d{3}[A-Z]{0,2})\b")
SPEC_RE = re.compile(r"-(\d{1,2})-(\d{1,2})-")


def specs_from_url(url: str) -> str:
    """Класс и толщина ламината из URL ('...-classic-russia-32-8-EPL198').

    Одно число — класс 31-34, другое — толщина в мм. Порядок в URL произвольный.
    """
    m = SPEC_RE.search(url)
    if not m:
        return ""
    a, b = int(m.group(1)), int(m.group(2))
    if 31 <= a <= 34:
        wear, thickness = a, b
    elif 31 <= b <= 34:
        wear, thickness = b, a
    else:
        return ""
    return f" {thickness}мм {wear}класс"


def fetch(url: str, retries: int = 3) -> BeautifulSoup | None:
    """GET с ретраями; None на 404 (карточка удалена)."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2)
    return None


def card_specs(soup: BeautifulSoup | None) -> str:
    """Размер/упаковку/метраж из карточки товара -> '1292x193x8мм (8шт/уп,1.9948кв.м)'."""
    if soup is None:
        return ""
    size = pack = meter = None
    for cois in soup.select(".cois"):
        label = cois.find(string=lambda s: s and s.strip())
        val_el = cois.select_one(".obm")
        if val_el is None:
            continue
        val = val_el.get_text(strip=True)
        key = (label or "").strip()
        if key.startswith("Размер доски"):
            size = val
        elif key.startswith("В упаковке"):
            pack = val
        elif key.startswith("Метраж"):
            meter = val
    parts = []
    if size:
        parts.append(f"{size.replace('x', '*')}мм")
    if pack or meter:
        inner = []
        if pack:
            inner.append(f"{pack}шт/уп")
        if meter:
            inner.append(f"{meter}кв.м")
        parts.append(f"({','.join(inner)})")
    return " ".join(parts).strip()


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
        url = urljoin(BASE, a.get("href", ""))
        out.append({
            "article": m.group(1) if m else "",
            "name": name + specs_from_url(url),
            "price": price,
            "url": url,
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
    for i, p in enumerate(products, 1):
        spec = card_specs(fetch(p["url"]))
        if spec:
            p["name"] = f"{p['name']} {spec}"
        if i % 20 == 0:
            print(f"  карточки: {i}/{len(products)}")
        time.sleep(0.3)
    return products


def main():
    products = scrape()
    if not products:
        raise SystemExit("Не найдено товаров — изменилась структура сайта")
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
