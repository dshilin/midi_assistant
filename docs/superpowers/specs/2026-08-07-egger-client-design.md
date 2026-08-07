# Клиент egger: скрейпер каталога egger-laminate.ru

Дата: 2026-08-07. Ветка: `client-egger` (от `multi-client-architecture`).

## Цель

Добавить нового поставщика напольных покрытий egger-laminate.ru в
мультиклиентскую архитектуру по образцу клиента `midi`: отдельная папка
`clients/egger/` с конфигом и скрейпером вне ядра. Изменений в ядре нет.

## Что делаем

1. `clients/egger/config.toml` — `name = "Egger"`, `slug = "egger"`,
   `bot_token = ""`, `site_url = "https://egger-laminate.ru"`.
2. `clients/egger/scrape.py` (по образцу `clients/midi/scrape.py`):
   - Разделы: `/laminat/page=1..N` (последняя страница из ссылки «Последняя»),
     `/probkoviy-pol`, `/podlozhka` (без пагинации).
   - Карточка (одинакова на всех разделах): `<a href="/decor/...">` →
     `<div class="cbt">` → `<h4>Название</h4>`, цена в `.bbcp` (первая цена;
     может быть «цена по запросу»).
   - Артикул: regex `^([A-Z]{2,3}\d{3})\b` из названия — `EPL015` (ламинат),
     `EPC019` (пробка); у подложки артикула нет → пусто.
   - Вывод: `clients/egger/catalog.csv`, шапка `Артикул, Наименование, Цена, Ссылка`
     (utf-8-sig, как у midi).

## Запуск

```bash
python3 clients/egger/scrape.py
python -m app.ingest egger
```

Ingest сам создаёт схему БД клиента, грузит каталог и запускает GPT-парсер.

## Проверка

- `clients/egger/scrape.py` при запуске печатает число найденных товаров и
  пишет catalog.csv.
- `app.ingest egger` завершается с числом загруженных товаров.
- Существующие тесты ядра не меняются (79 тестов проходят).
