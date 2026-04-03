# YandexGPT Product Parser

This module parses product names from the `products.db` database using YandexGPT and extracts structured specifications into the `floor_covering_specs` table.

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
- `length_mm`: Length in millimeters
- `width_mm`: Width in millimeters
- `thickness_mm`: Thickness in millimeters
- `length_m`: Length in meters (if specified separately)
- `pieces_per_pack`: Number of pieces per pack
- `area_per_pack_m2`: Area in square meters per pack
- `packs_per_pallet`: Number of packs per pallet
- `wear_class`: Wear resistance class (e.g., 32класс, 33класс)

## Database Schema

### floor_covering_specs Table

```sql
CREATE TABLE floor_covering_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    product_type TEXT,
    brand TEXT,
    collection TEXT,
    model TEXT,
    length_mm REAL,
    width_mm REAL,
    thickness_mm REAL,
    length_m REAL,
    pieces_per_pack INTEGER,
    area_per_pack_m2 REAL,
    packs_per_pallet INTEGER,
    wear_class TEXT,
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
