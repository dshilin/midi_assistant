# In-stock filter + article scraping

## Goal

Обновлять `products.db` только товарами в наличии и собирать реальный артикул
товара со страницы каталога, а не угадывать его из названия через GPT.

## Scope

Included:
- Скрейпер берёт каталог по URL с фильтром `in_stock-is-y` (только в наличии).
- Колонка `article` в таблице `products` + миграция для существующих БД.
- Скрейпинг артикула из `<span class="js-replace-article" data-value="…">`.
- GPT-парсер **не определяет артикул** — берёт его строго из `products.article`
  и переносит в `floor_covering_specs.article`.
- Обновлённая документация (`PARSER_README.md`).

Not included:
- Отображение артикула в ответах агента-консультанта.
- Заход на отдельные страницы товаров (артикул берётся из карточки каталога).
- Очистка «осиротевших» строк `floor_covering_specs` при пересборе `products`.

## Architecture

Двухшаговый пайплайн без изменений в порядке запуска:

```text
scrape_products.py  ->  products (name, url, price, article)
parse_products_gpt.py  ->  floor_covering_specs (specs + article)
```

Артикул проходит сквозь пайплайн: скрейпер кладёт его в `products.article`,
парсер лишь переносит в `floor_covering_specs.article`. GPT артикул не трогает.

## Components

### `app/scrape_products.py`
- `URL` → `.../filter/in_stock-is-y/apply/?SHOWALL_1=1` (только в наличии, все
  позиции одной страницей — без пагинации).
- `create_database()`: колонка `article TEXT` + `ALTER TABLE` для старых БД.
- `scrape_page()`: 4-й элемент в `zip` — `.js-replace-article`; берём `data-value`
  (запасной вариант — текст).
- `save_products()`: `INSERT` c колонкой `article`.

### `app/parse_products_gpt.py`
- Из промпта убрано поле `article` — GPT его больше не извлекает.
- `parse_all_products()`: читает `article` из `products` (с проверкой наличия
  колонки через `PRAGMA table_info`) и безусловно проставляет `specs['article']`
  этим значением перед сохранением.

## Notes / риски

- Скрейпер сопоставляет поля карточек параллельно по индексу (`zip`). Допущение:
  у каждой карточки есть title/price/link/article. Смена вёрстки сайта требует
  перепроверки селекторов.
- Предполагается, что `.js-replace-article` присутствует в карточке каталога.
  Если элемент есть только на странице товара — потребуется обход по `url`.
- Запуск (scrape + parse) требует сети до `midiltd.ru` и YandexGPT; выполняется
  вручную вне этой правки.
