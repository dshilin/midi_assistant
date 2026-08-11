"""Одноразовый скрейпер каталога midiltd.ru (Bitrix) -> clients/midi/catalog.csv.

Скрипт вне ядра: его можно править под изменение структуры сайта — на агента
это не влияет. Запуск: python3 clients/midi/scrape.py
"""
import csv
import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://midiltd.ru/catalog/napolnye_pokrytiya/filter/in_stock-is-y/apply/?SHOWALL_1=1"
OUT = os.path.join(os.path.dirname(__file__), "catalog.csv")


def scrape(url: str) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return [
        {
            "article": (el.get("data-value") or "").strip() if el else "",
            "name": n.get_text(strip=True),
            "price": p.get_text(strip=True) if p else "",
            "url": urljoin(url, a.get("href", "")) if a else "",
        }
        for n, p, a, el in zip(
            soup.select(".catalog-block__info-title"),
            soup.select(".price__new-val"),
            soup.select(".dark_link.switcher-title"),
            soup.select(".js-replace-article"),
        )
    ]


def main():
    products = scrape(URL)
    print(f"Найдено: {len(products)}")
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Артикул", "Наименование", "Цена", "Ссылка"])
        for p in products:
            if p["name"]:
                w.writerow([p["article"] or "", p["name"], p["price"] or "", p["url"] or ""])
    print(f"Каталог сохранён: {OUT}")


if __name__ == "__main__":
    main()
