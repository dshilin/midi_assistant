# midi_assistant

AI-консультант по напольным покрытиям для сайта и Telegram. Диалог ведёт FSM-агент,
товары ищутся в SQLite-базе `products.db`, доступность берётся только из складской
таблицы `stock`.

## Что внутри

- `app/main.py` — FastAPI: `GET /` отдаёт `static/chat.html`, `POST /chat` запускает агента.
- `app/tg_bot.py` — Telegram-интерфейс через aiogram 3.
- `app/agent_fsm.py` — сценарий консультанта: discovery → selection → calculation → closing.
- `app/db.py` — поиск товаров, выбор по ID и расчёт упаковок.
- `app/scrape_products.py` — загрузка каталога midiltd.ru в таблицу `products`.
- `app/parse_products_gpt.py` — разбор названий товаров через YandexGPT в `floor_covering_specs`.
- `app/load_stock.py` — загрузка остатков 1С из `.xlsx` в таблицу `stock`.

## Доступность товаров

Таблица `stock` — единственный источник доступности для консультанта.

Товар показывается и выбирается только если:

```sql
products.article = stock.article AND stock.quantity > 0
```

Товары без артикула, без строки в `stock` или с остатком `<= 0` не попадают в поиск
и не проходят выбор по ID.

## Быстрый старт

```bash
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:

```env
LLM_PROVIDER=openai
LLM_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Для YandexGPT и парсера товаров
YC_API_KEY=...
YC_FOLDER_ID=...

# Для Telegram-бота
TELEGRAM_BOT_TOKEN=...
```

## Подготовка базы

Запускайте шаги по порядку:

```bash
python3 -m app.scrape_products
python3 -m app.parse_products_gpt
python3 -m app.load_stock "Остатки на 09.08.26.xlsx"
```

Что делают шаги:

- `scrape_products` полностью пересобирает `products` и сохраняет `name`, `url`, `price`, `article`.
- `parse_products_gpt` заполняет `floor_covering_specs`; артикул не угадывает, а переносит из `products.article`.
- `load_stock` полностью пересобирает `stock` из выгрузки 1С: A — артикул, C — номенклатура, G — ед. изм., K — конечный остаток.

Подробности пайплайна: `PARSER_README.md`.

## Запуск

Web-интерфейс:

```bash
uvicorn app.main:app --reload
```

Telegram-бот:

```bash
python3 -m app.tg_bot
```

## Поиск и расчёт

Консультант хранит состояние пользователя в памяти процесса: тип покрытия, цвет,
бренд, площадь, выбранный товар и стадию диалога.

Поиск поддерживает:

- тип покрытия по `floor_covering_specs.product_type` и `products.name`;
- бренд по `floor_covering_specs.brand`;
- цвет с группами синонимов, например `темный` ищет также `черный`, `венге`, `графит`;
- нормализацию `ё → е` и игнорирование строкового `"null"`.

Расчёт материалов использует `area_per_pack_m2` выбранного товара и запас 10%.

## Тесты

```bash
python3 -m pytest tests/ -v
```

## Логи

Парсер пишет подробные логи в `logs/parser_YYYY-MM-DD.log`; каталог `logs/`
исключён из git.

## Безопасность

`.env` содержит ключи API и Telegram-токен. Не коммитьте его; файл исключён через
`.gitignore`.
