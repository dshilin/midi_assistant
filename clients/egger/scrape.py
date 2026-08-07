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
