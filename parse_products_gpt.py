import sqlite3
import json
import os
import asyncio
from yandex_gpt import YandexGPT, YandexGPTConfigManagerForAPIKey

DB_PATH = "products.db"
FOLDER_ID = os.getenv("YC_FOLDER_ID", "")
API_KEY = os.getenv("YC_API_KEY", "")


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
            length_mm REAL,
            width_mm REAL,
            thickness_mm REAL,
            length_m REAL,
            pieces_per_pack INTEGER,
            area_per_pack_m2 REAL,
            packs_per_pallet INTEGER,
            wear_class TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.commit()


async def get_yandex_gpt_response(text: str) -> str:
    """Send text to YandexGPT and get parsed response."""
    if not API_KEY or not FOLDER_ID:
        print("Error: YC_API_KEY and YC_FOLDER_ID environment variables must be set")
        return None
    
    # Initialize YandexGPT SDK
    config = YandexGPTConfigManagerForAPIKey(
        model_type="yandexgpt",
        catalog_id=FOLDER_ID,
        api_key=API_KEY
    )
    yandex_gpt = YandexGPT(config_manager=config)
    
    # Prepare the prompt for GPT
    prompt = f"""Проанализируй название напольного покрытия и извлеки следующие характеристики в формате JSON:

Название: {text}

Извлеки следующие поля (если информация отсутствует, укажи null):
- product_type: тип продукта (например: Ламинат, Винил, LVT, SPC, Кварц-винил)
- brand: бренд/производитель
- collection: коллекция
- model: модель/название дизайна
- length_mm: длина в мм (число)
- width_mm: ширина в мм (число)
- thickness_mm: толщина в мм (число)
- length_m: длина в метрах (число, если указана отдельно)
- pieces_per_pack: количество штук в упаковке (число)
- area_per_pack_m2: площадь в м2 в упаковке (число)
- packs_per_pallet: количество упаковок на паллете (число)
- wear_class: класс износостойкости (например: 32класс, 33класс)

Верни ТОЛЬКО JSON объект без дополнительного текста. Пример формата:
{{"product_type": "Ламинат", "brand": "EUROHOME", "collection": "MAJESTIC", "model": "Дуб Викинг Золотой", "length_mm": 1285, "width_mm": 192, "thickness_mm": 8, "length_m": null, "pieces_per_pack": 9, "area_per_pack_m2": 2.22, "packs_per_pallet": 52, "wear_class": "33класс"}}"""

    try:
        # Use YandexGPT via SDK
        messages = [
            {"role": "system", "text": "Ты - эксперт по parsingу названий напольных покрытий. Извлекай структурированные данные из текстов."},
            {"role": "user", "text": prompt}
        ]
        
        completion = await yandex_gpt.get_async_completion(messages=messages)
        response_text = completion.get("alternatives", [{}])[0].get("message", {}).get("text", "")
        return response_text
        
    except Exception as e:
        print(f"Error calling YandexGPT: {e}")
        return None


async def parse_product_name_with_gpt(product_name: str) -> dict:
    """Parse product name using YandexGPT and return structured data."""
    response = await get_yandex_gpt_response(product_name)
    
    if not response:
        return None
    
    try:
        # Try to extract JSON from response (GPT might add extra text)
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1
        
        if start_idx != -1 and end_idx != 0:
            json_str = response[start_idx:end_idx]
            parsed_data = json.loads(json_str)
            return parsed_data
        else:
            print(f"No JSON found in GPT response for: {product_name}")
            return None
            
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from GPT response: {e}")
        print(f"Response: {response}")
        return None


def save_parsed_specs(conn, product_id: int, specs: dict):
    """Save parsed specifications to floor_covering_specs table."""
    cursor = conn.cursor()
    
    # Check if entry already exists
    cursor.execute("SELECT id FROM floor_covering_specs WHERE product_id = ?", (product_id,))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing record
        cursor.execute("""
            UPDATE floor_covering_specs SET
                product_type = ?,
                brand = ?,
                collection = ?,
                model = ?,
                length_mm = ?,
                width_mm = ?,
                thickness_mm = ?,
                length_m = ?,
                pieces_per_pack = ?,
                area_per_pack_m2 = ?,
                packs_per_pallet = ?,
                wear_class = ?
            WHERE product_id = ?
        """, (
            specs.get('product_type'),
            specs.get('brand'),
            specs.get('collection'),
            specs.get('model'),
            specs.get('length_mm'),
            specs.get('width_mm'),
            specs.get('thickness_mm'),
            specs.get('length_m'),
            specs.get('pieces_per_pack'),
            specs.get('area_per_pack_m2'),
            specs.get('packs_per_pallet'),
            specs.get('wear_class'),
            product_id
        ))
    else:
        # Insert new record
        cursor.execute("""
            INSERT INTO floor_covering_specs (
                product_id, product_type, brand, collection, model,
                length_mm, width_mm, thickness_mm, length_m,
                pieces_per_pack, area_per_pack_m2, packs_per_pallet, wear_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            specs.get('product_type'),
            specs.get('brand'),
            specs.get('collection'),
            specs.get('model'),
            specs.get('length_mm'),
            specs.get('width_mm'),
            specs.get('thickness_mm'),
            specs.get('length_m'),
            specs.get('pieces_per_pack'),
            specs.get('area_per_pack_m2'),
            specs.get('packs_per_pallet'),
            specs.get('wear_class')
        ))
    
    conn.commit()


async def parse_all_products(conn):
    """Parse all products and save to floor_covering_specs."""
    cursor = conn.cursor()
    
    # Get all products
    cursor.execute("SELECT id, name FROM products")
    products = cursor.fetchall()
    
    print(f"Found {len(products)} products to parse")
    
    for i, (product_id, product_name) in enumerate(products, 1):
        print(f"\n[{i}/{len(products)}] Parsing: {product_name}")
        
        # Parse with YandexGPT
        specs = await parse_product_name_with_gpt(product_name)
        
        if specs:
            # Save to database
            save_parsed_specs(conn, product_id, specs)
            print(f"  ✓ Saved: {specs.get('brand', 'N/A')} {specs.get('collection', 'N/A')} - {specs.get('model', 'N/A')}")
        else:
            print(f"  ✗ Failed to parse")
        
        # Small delay to avoid rate limiting
        if i < len(products):
            import time
            await asyncio.sleep(0.5)
    
    print(f"\n{'='*60}")
    print("Parsing complete!")
    
    # Show summary
    cursor.execute("SELECT COUNT(*) FROM floor_covering_specs")
    total_parsed = cursor.fetchone()[0]
    print(f"Total records in floor_covering_specs: {total_parsed}")


async def main_async():
    """Main async function to orchestrate parsing."""
    print("Starting YandexGPT product parsing...")
    print(f"Database: {DB_PATH}")
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Create table
        create_floor_covering_specs_table(conn)
        print("✓ floor_covering_specs table created")
        
        # Parse all products
        await parse_all_products(conn)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def main():
    """Entry point that runs the async main function."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
