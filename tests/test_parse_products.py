import pytest
import sqlite3
import json
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.parse_products_gpt import (
    create_floor_covering_specs_table,
    save_parsed_specs,
    parse_product_name_with_gpt,
    get_yandex_gpt_response,
    parse_all_products,
)


@pytest.fixture
def db_connection():
    """Create in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT,
            price TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


@pytest.fixture
def sample_product():
    """Sample product data."""
    return {
        "id": 1,
        "name": "Ламинат EUROHOME MAJESTIC Дуб Викинг Золотой 1285*192*8мм (9шт/уп,2.22кв.м,52уп/пал) 33класс",
        "url": "https://example.com/product1",
        "price": "1500 руб"
    }


@pytest.fixture
def sample_specs():
    """Sample parsed specs."""
    return {
        "product_type": "Ламинат",
        "brand": "EUROHOME",
        "collection": "MAJESTIC",
        "model": "Дуб Викинг Золотой",
        "length_mm": 1285,
        "width_mm": 192,
        "thickness_mm": 8,
        "length_m": None,
        "pieces_per_pack": 9,
        "area_per_pack_m2": 2.22,
        "packs_per_pallet": 52,
        "wear_class": "33класс"
    }


class TestCreateFloorCoveringSpecsTable:
    """Tests for create_floor_covering_specs_table function."""

    def test_create_table(self, db_connection):
        """Test that table is created successfully."""
        create_floor_covering_specs_table(db_connection)
        
        cursor = db_connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='floor_covering_specs'")
        result = cursor.fetchone()
        
        assert result is not None
        assert result[0] == "floor_covering_specs"

    def test_create_table_idempotent(self, db_connection):
        """Test that calling create twice doesn't fail."""
        create_floor_covering_specs_table(db_connection)
        create_floor_covering_specs_table(db_connection)  # Should not raise
        
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM floor_covering_specs")
        assert cursor.fetchone()[0] == 0

    def test_table_schema(self, db_connection):
        """Test that table has correct schema."""
        create_floor_covering_specs_table(db_connection)
        
        cursor = db_connection.cursor()
        cursor.execute("PRAGMA table_info(floor_covering_specs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        expected_columns = {
            "id": "INTEGER",
            "product_id": "INTEGER",
            "product_type": "TEXT",
            "brand": "TEXT",
            "collection": "TEXT",
            "model": "TEXT",
            "length_mm": "REAL",
            "width_mm": "REAL",
            "thickness_mm": "REAL",
            "length_m": "REAL",
            "pieces_per_pack": "INTEGER",
            "area_per_pack_m2": "REAL",
            "packs_per_pallet": "INTEGER",
            "wear_class": "TEXT"
        }
        
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found"
            assert columns[col_name] == col_type, f"Column {col_name} has wrong type"


class TestSaveParsedSpecs:
    """Tests for save_parsed_specs function."""

    def test_insert_new_record(self, db_connection, sample_product, sample_specs):
        """Test inserting a new record."""
        create_floor_covering_specs_table(db_connection)
        
        # Insert product first
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT INTO products (id, name, url, price) VALUES (?, ?, ?, ?)",
            (sample_product["id"], sample_product["name"], sample_product["url"], sample_product["price"])
        )
        db_connection.commit()
        
        # Save specs
        save_parsed_specs(db_connection, sample_product["id"], sample_specs)
        
        # Verify
        cursor.execute("SELECT * FROM floor_covering_specs WHERE product_id = ?", (sample_product["id"],))
        result = cursor.fetchone()
        
        assert result is not None
        assert result[2] == "Ламинат"  # product_type
        assert result[3] == "EUROHOME"  # brand
        assert result[4] == "MAJESTIC"  # collection
        assert result[10] == 9  # pieces_per_pack
        assert result[11] == 2.22  # area_per_pack_m2

    def test_update_existing_record(self, db_connection, sample_product, sample_specs):
        """Test updating an existing record."""
        create_floor_covering_specs_table(db_connection)
        
        # Insert product
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT INTO products (id, name, url, price) VALUES (?, ?, ?, ?)",
            (sample_product["id"], sample_product["name"], sample_product["url"], sample_product["price"])
        )
        db_connection.commit()
        
        # Insert initial specs
        save_parsed_specs(db_connection, sample_product["id"], sample_specs)
        
        # Update with different specs
        updated_specs = sample_specs.copy()
        updated_specs["brand"] = "UPDATED_BRAND"
        updated_specs["pieces_per_pack"] = 10
        
        save_parsed_specs(db_connection, sample_product["id"], updated_specs)
        
        # Verify update
        cursor.execute("SELECT brand, pieces_per_pack FROM floor_covering_specs WHERE product_id = ?", 
                      (sample_product["id"],))
        result = cursor.fetchone()
        
        assert result[0] == "UPDATED_BRAND"
        assert result[1] == 10
        
        # Verify no duplicate
        cursor.execute("SELECT COUNT(*) FROM floor_covering_specs WHERE product_id = ?", 
                      (sample_product["id"],))
        assert cursor.fetchone()[0] == 1

    def test_save_with_null_values(self, db_connection, sample_product):
        """Test saving specs with null values."""
        create_floor_covering_specs_table(db_connection)
        
        # Insert product
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT INTO products (id, name, url, price) VALUES (?, ?, ?, ?)",
            (sample_product["id"], sample_product["name"], sample_product["url"], sample_product["price"])
        )
        db_connection.commit()
        
        # Specs with null values
        specs = {
            "product_type": "Ламинат",
            "brand": "EUROHOME",
            "collection": None,
            "model": None,
            "length_mm": 1285,
            "width_mm": None,
            "thickness_mm": None,
            "length_m": None,
            "pieces_per_pack": None,
            "area_per_pack_m2": None,
            "packs_per_pallet": None,
            "wear_class": "33класс"
        }
        
        save_parsed_specs(db_connection, sample_product["id"], specs)
        
        # Verify
        cursor.execute("SELECT product_type, collection, brand FROM floor_covering_specs WHERE product_id = ?", 
                      (sample_product["id"],))
        result = cursor.fetchone()
        
        assert result[0] == "Ламинат"
        assert result[1] is None
        assert result[2] == "EUROHOME"


class TestParseProductNameWithGPT:
    """Tests for parse_product_name_with_gpt function."""

    @pytest.mark.asyncio
    async def test_successful_parse(self):
        """Test successful JSON parsing from GPT response."""
        sample_response = """Вот результат анализа:
        {"product_type": "Ламинат", "brand": "EUROHOME", "collection": "MAJESTIC", "model": "Дуб Викинг", "length_mm": 1285, "width_mm": 192, "thickness_mm": 8, "length_m": null, "pieces_per_pack": 9, "area_per_pack_m2": 2.22, "packs_per_pallet": 52, "wear_class": "33класс"}
        """
        
        with patch("app.parse_products_gpt.get_yandex_gpt_response", new_callable=AsyncMock) as mock_gpt:
            mock_gpt.return_value = sample_response
            
            result = await parse_product_name_with_gpt("Test product name")
            
            assert result is not None
            assert result["product_type"] == "Ламинат"
            assert result["brand"] == "EUROHOME"
            assert result["collection"] == "MAJESTIC"
            assert result["length_mm"] == 1285

    @pytest.mark.asyncio
    async def test_no_response_from_gpt(self):
        """Test handling of None response from GPT."""
        with patch("app.parse_products_gpt.get_yandex_gpt_response", new_callable=AsyncMock) as mock_gpt:
            mock_gpt.return_value = None
            
            result = await parse_product_name_with_gpt("Test product")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        """Test handling of invalid JSON."""
        with patch("app.parse_products_gpt.get_yandex_gpt_response", new_callable=AsyncMock) as mock_gpt:
            mock_gpt.return_value = "This is not valid JSON at all"
            
            result = await parse_product_name_with_gpt("Test product")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_json_extraction_from_text(self):
        """Test extracting JSON from mixed text response."""
        sample_response = """Анализирую название...
        
        Вот извлеченные данные:
        {"product_type": "Винил", "brand": "TEST"}
        
        Надеюсь, это поможет!
        """
        
        with patch("app.parse_products_gpt.get_yandex_gpt_response", new_callable=AsyncMock) as mock_gpt:
            mock_gpt.return_value = sample_response
            
            result = await parse_product_name_with_gpt("Test product")
            
            assert result is not None
            assert result["product_type"] == "Винил"
            assert result["brand"] == "TEST"


class TestGetYandexGPTResponse:
    """Tests for get_yandex_gpt_response function."""

    @pytest.mark.asyncio
    async def test_missing_credentials(self):
        """Test handling of missing API credentials."""
        with patch("app.parse_products_gpt.API_KEY", ""), \
             patch("app.parse_products_gpt.FOLDER_ID", ""):
            
            result = await get_yandex_gpt_response("Test")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_successful_api_response(self):
        """Test successful API response."""
        with patch("app.parse_products_gpt.API_KEY", "test_key"), \
             patch("app.parse_products_gpt.FOLDER_ID", "test_folder"), \
             patch("app.parse_products_gpt.requests.post") as mock_post:
            
            mock_response = MagicMock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "result": {
                    "alternatives": [
                        {
                            "message": {
                                "text": '{"product_type": "Ламинат", "brand": "TEST"}'
                            }
                        }
                    ]
                }
            }
            mock_post.return_value = mock_response
            
            result = await get_yandex_gpt_response("Test product")
            
            assert result == '{"product_type": "Ламинат", "brand": "TEST"}'
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test handling of API errors."""
        with patch("app.parse_products_gpt.API_KEY", "test_key"), \
             patch("app.parse_products_gpt.FOLDER_ID", "test_folder"), \
             patch("app.parse_products_gpt.requests.post") as mock_post:
            
            mock_response = MagicMock()
            mock_response.ok = False
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_post.return_value = mock_response
            
            result = await get_yandex_gpt_response("Test product")
            
            assert result is None


class TestParseAllProducts:
    """Tests for parse_all_products function."""

    @pytest.mark.asyncio
    async def test_parse_all_products_success(self, db_connection, sample_product, sample_specs):
        """Test parsing all products successfully."""
        create_floor_covering_specs_table(db_connection)
        
        # Insert sample product
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT INTO products (id, name, url, price) VALUES (?, ?, ?, ?)",
            (sample_product["id"], sample_product["name"], sample_product["url"], sample_product["price"])
        )
        db_connection.commit()
        
        with patch("app.parse_products_gpt.parse_product_name_with_gpt", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = sample_specs
            
            await parse_all_products(db_connection)
            
            # Verify product was parsed
            cursor.execute("SELECT COUNT(*) FROM floor_covering_specs")
            count = cursor.fetchone()[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_parse_all_products_with_failures(self, db_connection, sample_product):
        """Test parsing with some failures."""
        create_floor_covering_specs_table(db_connection)
        
        # Insert sample product
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT INTO products (id, name, url, price) VALUES (?, ?, ?, ?)",
            (sample_product["id"], sample_product["name"], sample_product["url"], sample_product["price"])
        )
        db_connection.commit()
        
        with patch("app.parse_products_gpt.parse_product_name_with_gpt", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = None  # Simulate failure
            
            await parse_all_products(db_connection)
            
            # Verify no specs were saved
            cursor.execute("SELECT COUNT(*) FROM floor_covering_specs")
            count = cursor.fetchone()[0]
            assert count == 0

    @pytest.mark.asyncio
    async def test_parse_empty_database(self, db_connection):
        """Test parsing with empty database."""
        create_floor_covering_specs_table(db_connection)
        
        with patch("app.parse_products_gpt.parse_product_name_with_gpt", new_callable=AsyncMock) as mock_parse:
            await parse_all_products(db_connection)
            
            mock_parse.assert_not_called()


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, db_connection, sample_product):
        """Test complete workflow from product to specs."""
        # Setup
        cursor = db_connection.cursor()
        cursor.execute(
            "INSERT INTO products (id, name, url, price) VALUES (?, ?, ?, ?)",
            (sample_product["id"], sample_product["name"], sample_product["url"], sample_product["price"])
        )
        db_connection.commit()
        
        create_floor_covering_specs_table(db_connection)
        
        # Mock GPT response
        sample_response = json.dumps({
            "product_type": "Ламинат",
            "brand": "EUROHOME",
            "collection": "MAJESTIC",
            "model": "Дуб Викинг Золотой",
            "length_mm": 1285,
            "width_mm": 192,
            "thickness_mm": 8,
            "length_m": None,
            "pieces_per_pack": 9,
            "area_per_pack_m2": 2.22,
            "packs_per_pallet": 52,
            "wear_class": "33класс"
        })
        
        with patch("app.parse_products_gpt.get_yandex_gpt_response", new_callable=AsyncMock) as mock_gpt:
            mock_gpt.return_value = sample_response
            
            # Execute
            await parse_all_products(db_connection)
            
            # Verify
            cursor.execute("""
                SELECT product_type, brand, collection, model, length_mm, width_mm, 
                       thickness_mm, pieces_per_pack, area_per_pack_m2, packs_per_pallet, wear_class
                FROM floor_covering_specs 
                WHERE product_id = ?
            """, (sample_product["id"],))
            
            result = cursor.fetchone()
            
            assert result is not None
            assert result[0] == "Ламинат"
            assert result[1] == "EUROHOME"
            assert result[2] == "MAJESTIC"
            assert result[3] == "Дуб Викинг Золотой"
            assert result[4] == 1285
            assert result[5] == 192
            assert result[6] == 8
            assert result[7] == 9
            assert result[8] == 2.22
            assert result[9] == 52
            assert result[10] == "33класс"
