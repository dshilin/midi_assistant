import sqlite3
import json
import os
import asyncio
import argparse
import requests
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
load_dotenv()

DB_PATH = "products.db"
FOLDER_ID = os.getenv("YC_FOLDER_ID", "")
API_KEY = os.getenv("YC_API_KEY", "")
API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Configure logger
logger.add(
    "logs/parser_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
    encoding="utf-8"
)
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)


def create_floor_covering_specs_table(conn):
    """Create floor_covering_specs table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS floor_covering_specs (
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
        )
    """)
    conn.commit()
    logger.debug("floor_covering_specs table verified/created")


async def get_yandex_gpt_response(text: str) -> str:
    """Send text to YandexGPT and get parsed response."""
    if not API_KEY or not FOLDER_ID:
        logger.error("YC_API_KEY and YC_FOLDER_ID environment variables must be set")
        return None

    logger.debug(f"Sending request to YandexGPT for text: {text[:50]}...")

    # Prepare the prompt for GPT
    prompt = f"""Проанализируй название напольного покрытия и извлеки следующие характеристики в формате JSON.

Название: {text}

ДОПУСТИМЫЕ ЗНАЧЕНИЯ ЦВЕТА (color):
- белый, черный, серый, темный, светлый
- коричневый, бежевый, золотой, серебристый
- красный, синий, зеленый, желтый, розовый, фиолетовый, оранжевый, голубой
- венге, графит

ПРАВИЛА РАЗБОРА:
1. product_type — тип продукта (первое слово): Ламинат, Винил, LVT, SPC, Кварц-винил и т.д.
2. brand — бренд/производитель (обычно первое-третье слово, заглавными буквами): EUROHOME, FLOORPAN, KRONOSPAN, KRONOSTAR и т.д.
3. collection — коллекция (обычно одно-два слова ПОСЛЕ бренда, часто заглавными): MAJESTIC, LOFT, GREY, Atlantic, Дубов и т.д.
4. model — название модели/дизайна (всё что ПОСЛЕ коллекции и ДО размеров): Дуб Викинг Золотой, Ройбуш, Эрл Грей, Улун и т.д.
5. color — цвет покрытия. ДОЛЖЕН быть заполнен ВСЕГДА. Никогда не ставь null.
   - Если в названии есть явное указание цвета (Золотой, Белый, Серый, Солнечный и т.д.) — используй его.
   - Если в названии есть слово "GREY" или "Grey" — ставь "серый".
   - Если в названии есть слово "WHITE" или "White" — ставь "белый".
   - Если цвет явно не указан — определи по породе дерева:
     * "дуб" → "коричневый" (если нет уточнения светлый/тёмный/белый)
     * "сосна" → "светлый"
     * "вишня" → "красный"
     * "орех" → "коричневый"
     * "венге" → "венге"
   - Выбери ОДИН цвет из списка допустимых значений.
6. Размеры: ищи паттерн ЧИСЛО*ЧИСЛО*ЧИСЛОмм (например: 1285*192*8мм)
   - length_mm — первое число
   - width_mm — второе число  
   - thickness_mm — третье число
7. Упаковка: ищи паттерн в скобках (ЧИСЛОшт/уп, ЧИСЛОкв.м, ЧИСЛОуп/пал)
   - pieces_per_pack — количество штук
   - area_per_pack_m2 — площадь в м2
   - packs_per_pallet — количество упаковок на паллете
8. wear_class — класс износостойкости в конце: 32класс, 33класс и т.д.

ВАЖНО:
- Collection и model — это РАЗНЫЕ поля. Collection обычно короткое (1-2 слова), model — название дизайна.
- НЕ объединяй collection и model в одно поле!
- Если после бренда идёт одно слово заглавными буквами — это скорее всего collection.
- Всё что после collection и до размеров — это model.
- Поле color НИКОГДА не должно быть null. Если сомневаешься — выбери ближайший цвет из списка допустимых.

Извлеки следующие поля (если информация отсутствует, укажи null):
- product_type: тип продукта
- brand: бренд/производитель
- collection: коллекция
- model: модель/название дизайна
- color: цвет покрытия (ОБЯЗАТЕЛЬНОЕ поле, не может быть null)
- length_mm: длина в мм (число)
- width_mm: ширина в мм (число)
- thickness_mm: толщина в мм (число)
- length_m: длина в метрах (число, если указана отдельно)
- pieces_per_pack: количество штук в упаковке (число)
- area_per_pack_m2: площадь в м2 в упаковке (число)
- packs_per_pallet: количество упаковок на паллете (число)
- wear_class: класс износостойкости

Примеры правильного разбора:

Пример 1:
Название: "Ламинат EUROHOME MAJESTIC Дуб Викинг Золотой 1285*192*8мм (9шт/уп,2.22кв.м,52уп/пал) 33класс"
Результат: {{"product_type": "Ламинат", "brand": "EUROHOME", "collection": "MAJESTIC", "model": "Дуб Викинг Золотой", "color": "золотой", "length_mm": 1285, "width_mm": 192, "thickness_mm": 8, "length_m": null, "pieces_per_pack": 9, "area_per_pack_m2": 2.22, "packs_per_pallet": 52, "wear_class": "33класс"}}

Пример 2:
Название: "Ламинат FLOORPAN GREY Ройбуш 1380*193*8мм (8шт/уп,2.131кв.м,60уп/пал) 32класс"
Результат: {{"product_type": "Ламинат", "brand": "FLOORPAN", "collection": "GREY", "model": "Ройбуш", "color": "серый", "length_mm": 1380, "width_mm": 193, "thickness_mm": 8, "length_m": null, "pieces_per_pack": 8, "area_per_pack_m2": 2.131, "packs_per_pallet": 60, "wear_class": "32класс"}}

Пример 3:
Название: "Ламинат Дуб Ахад GH2304 1380*193*8мм (8шт/уп,2,13кв.м) 32класс"
Результат: {{"product_type": "Ламинат", "brand": null, "collection": null, "model": "Дуб Ахад", "color": "коричневый", "length_mm": 1380, "width_mm": 193, "thickness_mm": 8, "length_m": null, "pieces_per_pack": 8, "area_per_pack_m2": 2.13, "packs_per_pallet": null, "wear_class": "32класс"}}

Верни ТОЛЬКО JSON объект без дополнительного текста."""

    try:
        # Build model URI
        model_uri = f"gpt://{FOLDER_ID}/yandexgpt-lite/latest"

        # Prepare headers and payload
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        messages = [
            {"role": "system", "text": "Ты - эксперт по parsingу названий напольных покрытий. Извлекай структурированные данные из текстов."},
            {"role": "user", "text": prompt}
        ]

        payload = {
            "modelUri": model_uri,
            "completionOptions": {
                "stream": False,
                "temperature": 0.0,
                "maxTokens": 1000,
            },
            "messages": messages,
        }

        logger.debug(f"Calling YandexGPT API: {API_URL}")
        logger.debug(f"Model URI: {model_uri}")

        # Use requests (sync) since YandexGPT API doesn't require async
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.ok:
            result = response.json()
            response_text = result["result"]["alternatives"][0]["message"]["text"]
            logger.debug(f"Received response from YandexGPT ({len(response_text)} chars)")
            return response_text
        else:
            logger.error(f"YandexGPT API error {response.status_code}: {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error("YandexGPT request timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"YandexGPT request error: {e}")
        return None
    except KeyError as e:
        logger.error(f"YandexGPT response parsing error: {e}")
        return None


async def parse_product_name_with_gpt(product_name: str) -> dict:
    """Parse product name using YandexGPT and return structured data."""
    response = await get_yandex_gpt_response(product_name)
    
    if not response:
        logger.warning(f"No response from YandexGPT for: {product_name}")
        return None
    
    try:
        # Try to extract JSON from response (GPT might add extra text)
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx != -1 and end_idx != 0:
            json_str = response[start_idx:end_idx]
            parsed_data = json.loads(json_str)
            logger.debug(f"Successfully parsed JSON for: {product_name[:50]}...")
            return parsed_data
        else:
            logger.warning(f"No JSON found in GPT response for: {product_name}")
            return None
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from GPT response: {e}")
        logger.debug(f"Response: {response}")
        return None


def save_parsed_specs(conn, product_id: int, specs: dict):
    """Save parsed specifications to floor_covering_specs table."""
    cursor = conn.cursor()
    
    # Check if entry already exists
    cursor.execute("SELECT id FROM floor_covering_specs WHERE product_id = ?", (product_id,))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute("""
            UPDATE floor_covering_specs SET
                product_type = ?,
                brand = ?,
                collection = ?,
                model = ?,
                color = ?,
                length_mm = ?,
                width_mm = ?,
                thickness_mm = ?,
                length_m = ?,
                pieces_per_pack = ?,
                area_per_pack_m2 = ?,
                packs_per_pallet = ?,
                wear_class = ?,
                article = ?
            WHERE product_id = ?
        """, (
            specs.get('product_type'),
            specs.get('brand'),
            specs.get('collection'),
            specs.get('model'),
            specs.get('color'),
            specs.get('length_mm'),
            specs.get('width_mm'),
            specs.get('thickness_mm'),
            specs.get('length_m'),
            specs.get('pieces_per_pack'),
            specs.get('area_per_pack_m2'),
            specs.get('packs_per_pallet'),
            specs.get('wear_class'),
            specs.get('article'),
            product_id
        ))
        logger.debug(f"Updated existing record for product_id={product_id}")
    else:
        cursor.execute("""
            INSERT INTO floor_covering_specs (
                product_id, product_type, brand, collection, model, color,
                length_mm, width_mm, thickness_mm, length_m,
                pieces_per_pack, area_per_pack_m2, packs_per_pallet, wear_class,
                article
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            specs.get('product_type'),
            specs.get('brand'),
            specs.get('collection'),
            specs.get('model'),
            specs.get('color'),
            specs.get('length_mm'),
            specs.get('width_mm'),
            specs.get('thickness_mm'),
            specs.get('length_m'),
            specs.get('pieces_per_pack'),
            specs.get('area_per_pack_m2'),
            specs.get('packs_per_pallet'),
            specs.get('wear_class'),
            specs.get('article')
        ))
        logger.debug(f"Inserted new record for product_id={product_id}")
    
    conn.commit()


async def parse_all_products(conn, product_ids=None):
    """Parse all products or specific product IDs.
    
    Args:
        conn: Database connection
        product_ids: Optional list of product IDs to parse. If None, parses all products.
    """
    cursor = conn.cursor()

    # Артикул берётся ТОЛЬКО скрейпером со страницы товара (products.article).
    # GPT артикул не определяет — см. промпт.
    has_article = any(row[1] == "article" for row in cursor.execute("PRAGMA table_info(products)"))
    columns = "id, name, article" if has_article else "id, name"

    # Get products - either specific IDs or all
    if product_ids:
        placeholders = ','.join('?' for _ in product_ids)
        cursor.execute(f"SELECT {columns} FROM products WHERE id IN ({placeholders})", product_ids)
        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} products for IDs: {product_ids}")
    else:
        cursor.execute(f"SELECT {columns} FROM products")
        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} products to parse")

    # Нормализуем к (id, name, article) независимо от наличия колонки.
    products = [(r[0], r[1], (r[2] if has_article else None)) for r in rows]

    success_count = 0
    fail_count = 0

    for i, (product_id, product_name, scraped_article) in enumerate(products, 1):
        logger.info(f"[{i}/{len(products)}] Parsing: {product_name}")

        # Parse with YandexGPT
        specs = await parse_product_name_with_gpt(product_name)

        # Артикул проставляется только из данных скрейпера (products.article).
        # GPT его не определяет, поэтому перезаписываем безусловно.
        if specs is not None:
            specs['article'] = scraped_article

        if specs:
            # Save to database
            save_parsed_specs(conn, product_id, specs)
            logger.success(f"Saved: {specs.get('brand', 'N/A')} {specs.get('collection', 'N/A')} - {specs.get('model', 'N/A')}")
            success_count += 1
        else:
            logger.error(f"Failed to parse: {product_name}")
            fail_count += 1
        
        # Small delay to avoid rate limiting
        if i < len(products):
            await asyncio.sleep(0.5)
    
    logger.info("=" * 60)
    logger.info("Parsing complete!")
    logger.info(f"Total records in floor_covering_specs: {cursor.execute('SELECT COUNT(*) FROM floor_covering_specs').fetchone()[0]}")
    logger.success(f"Successfully parsed: {success_count}")
    logger.error(f"Failed: {fail_count}")


async def main_async(product_ids=None):
    """Main async function to orchestrate parsing.
    
    Args:
        product_ids: Optional list of product IDs to parse. If None, parses all products.
    """
    logger.info("Starting YandexGPT product parsing...")
    logger.info(f"Database: {DB_PATH}")
    if product_ids:
        logger.info(f"Parsing specific product IDs: {product_ids}")
    else:
        logger.info("Parsing ALL products")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Create table
        create_floor_covering_specs_table(conn)
        logger.success("floor_covering_specs table created/verified")
        
        # Parse all products
        await parse_all_products(conn, product_ids=product_ids)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.exception("Traceback:")
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")


def main():
    """Entry point that runs the async main function."""
    parser = argparse.ArgumentParser(
        description='Parse product names from database using YandexGPT',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse all products
  python parse_products_gpt.py
  
  # Parse specific product by ID
  python parse_products_gpt.py --id 70
  
  # Parse multiple products by IDs
  python parse_products_gpt.py --ids 70,71,72
        """
    )
    
    parser.add_argument(
        '--id',
        type=int,
        help='Parse a single product by ID'
    )
    
    parser.add_argument(
        '--ids',
        type=str,
        help='Parse multiple products by comma-separated IDs (e.g., 70,71,72)'
    )
    
    args = parser.parse_args()
    
    # Determine which products to parse
    product_ids = None  # None means parse all
    
    if args.id:
        product_ids = [args.id]
    elif args.ids:
        try:
            product_ids = [int(x.strip()) for x in args.ids.split(',')]
        except ValueError:
            logger.error("Invalid IDs format. Use comma-separated integers (e.g., 70,71,72)")
            raise SystemExit(1)
    
    try:
        asyncio.run(main_async(product_ids=product_ids))
    except KeyboardInterrupt:
        logger.warning("Parsing interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
