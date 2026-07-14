# Data Pipeline: Scraper + YandexGPT Parser

Наполнение `products.db` состоит из двух шагов, которые запускаются по порядку:

1. **`app/scrape_products.py`** — скрейпит каталог напольных покрытий с сайта
   midiltd.ru в таблицу `products` (название, url, цена, **артикул**).
2. **`app/parse_products_gpt.py`** — прогоняет названия из `products` через
   YandexGPT и раскладывает их в структурированную таблицу `floor_covering_specs`.
3. **`app/load_stock.py`** — загружает остатки со склада (выгрузка 1С в `.xlsx`)
   в таблицу `stock`; связывается с товарами по артикулу.

## Источник данных (in-stock)

Скрейпер берёт **только товары в наличии** одной страницей — используется
отфильтрованный URL с `SHOWALL_1=1` (вывод всех позиций без пагинации):

```
https://midiltd.ru/catalog/napolnye_pokrytiya/filter/in_stock-is-y/apply/?SHOWALL_1=1
```

## Шаг 1. Скрейпинг

```bash
python -m app.scrape_products
```

- Каждый запуск **полностью пересобирает** таблицу `products` (`DELETE FROM products`).
- Артикул берётся из элемента карточки
  `<span class="js-replace-article" data-value="01-38802">` (значение `data-value`).
- Все товары грузятся одной страницей за счёт `SHOWALL_1=1` — пагинация не нужна.

> ⚠️ Скрейпер сопоставляет поля карточек параллельно по индексу
> (`zip` по спискам title/price/link/article). Это подразумевает, что у каждой
> карточки эти элементы присутствуют. Если сайт сменит вёрстку — проверить
> соответствие селекторов.

## Шаг 2. Парсинг названий (YandexGPT)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Yandex Cloud Credentials

Set the following environment variables:

```bash
export YC_API_KEY="your_yandex_cloud_api_key"
export YC_FOLDER_ID="your_yandex_cloud_folder_id"
```

You can obtain these from the [Yandex Cloud Console](https://console.cloud.yandex.ru/).

## Usage

Run the parser:

```bash
python parse_products_gpt.py
```

The script will:
1. Read all product names from the `products` table
2. Send each name to YandexGPT for parsing
3. Extract structured data and save it to `floor_covering_specs` table

## Extracted Fields

The parser extracts the following fields from product names:

- `product_type`: Product type (e.g., Ламинат, Винил, LVT, SPC)
- `brand`: Brand/manufacturer
- `collection`: Collection name
- `model`: Model/design name
- `color`: Colour of the covering (белый, серый, венге, графит, …)
- `length_mm`: Length in millimeters
- `width_mm`: Width in millimeters
- `thickness_mm`: Thickness in millimeters
- `length_m`: Length in meters (if specified separately)
- `pieces_per_pack`: Number of pieces per pack
- `area_per_pack_m2`: Area in square meters per pack
- `packs_per_pallet`: Number of packs per pallet
- `wear_class`: Wear resistance class (e.g., 32класс, 33класс)

> **Артикул GPT не извлекает.** Поле `floor_covering_specs.article` заполняется
> строго значением, собранным скрейпером со страницы (`products.article`).
> Парсер лишь переносит его в таблицу спецификаций.

## Остатки со склада (app.load_stock)

Остатки приходят отдельной выгрузкой из 1С («Ведомость по товарам на складах»,
`.xlsx`) и загружаются в таблицу `stock`:

```bash
python -m app.load_stock "Остатки на 09.08.26.xlsx"
```

- Значимые колонки листа: **A — Артикул**, C — Номенклатура, G — Ед. изм.,
  **K — Конечный остаток**.
- Каждый запуск полностью пересобирает таблицу `stock` (`DELETE FROM stock`).
- Читается стандартной библиотекой (zip+xml), без openpyxl/pandas.
- Связь с каталогом — по артикулу: `stock.article` ↔ `products.article`. Поэтому
  остатки стыкуются только после того, как скрейпер собрал артикулы товаров.

## Database Schema

### stock Table (заполняет app.load_stock)

```sql
CREATE TABLE stock (
    article TEXT PRIMARY KEY,
    name TEXT,
    unit TEXT,
    quantity REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### products Table (заполняет скрейпер)

```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT,
    price TEXT,
    article TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### floor_covering_specs Table (заполняет GPT-парсер)

```sql
CREATE TABLE floor_covering_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    product_type TEXT,
    brand TEXT,
    collection TEXT,
    model TEXT,
    color TEXT,
    length_mm REAL,
    width_mm REAL,
    thickness_mm REAL,
    length_m REAL,
    pieces_per_pack INTEGER,
    area_per_pack_m2 REAL,
    packs_per_pallet INTEGER,
    wear_class TEXT,
    article TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

## Example

**Input Product Name:**
```
Ламинат EUROHOME MAJESTIC Дуб Викинг Золотой 1285*192*8мм (9шт/уп,2.22кв.м,52уп/пал) 33класс
```

**Output:**
```json
{
  "product_type": "Ламинат",
  "brand": "EUROHOME",
  "collection": "MAJESTIC",
  "model": "Дуб Викинг Золотой",
  "length_mm": 1285,
  "width_mm": 192,
  "thickness_mm": 8,
  "length_m": null,
  "pieces_per_pack": 9,
  "area_per_pack_m2": 2.22,
  "packs_per_pallet": 52,
  "wear_class": "33класс"
}
```

## Notes

- The script processes products sequentially with a 0.5s delay between requests to avoid rate limiting
- If a field cannot be extracted, it will be set to `null`
- The script updates existing records if they already exist (no duplicates)
- Progress is displayed in the console during execution
