import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urljoin

# Фильтр in_stock-is-y — только в наличии; SHOWALL_1=1 — все товары одной страницей (без пагинации).
URL = "https://midiltd.ru/catalog/napolnye_pokrytiya/filter/in_stock-is-y/apply/?SHOWALL_1=1"
DB_PATH = "products.db"


def create_database():
    """Create SQLite database and products table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT,
            price TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add article column if not exists (migration)
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(products)")}
    if "article" not in existing_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN article TEXT")
    # Clear existing data to avoid duplicates
    cursor.execute("DELETE FROM products")
    conn.commit()
    return conn


def scrape_products(url):
    """Scrape product names from the given URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    products = []

    # Current site (Bitrix) uses these selectors
    for name_elem, price_elem, link_elem, article_elem in zip(
        soup.select(".catalog-block__info-title"),
        soup.select(".price__new-val"),
        soup.select(".dark_link.switcher-title"),
        soup.select(".js-replace-article"),
    ):
        name = name_elem.get_text(strip=True)
        if not name:
            continue
        price = price_elem.get_text(strip=True) if price_elem else None
        href = link_elem.get("href", "") if link_elem else None
        product_url = urljoin(url, href) if href else None
        article = None
        if article_elem:
            article = article_elem.get("data-value") or article_elem.get_text(strip=True) or None
        products.append((name, product_url, price, article))

    return products


def save_products(conn, products):
    """Save products to the database."""
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO products (name, url, price, article) VALUES (?, ?, ?, ?)",
        products
    )
    conn.commit()
    return cursor.rowcount


def main():
    print(f"Scraping products from: {URL}")
    
    # Create database
    conn = create_database()
    print(f"Database created: {DB_PATH}")
    
    # Scrape products
    products = scrape_products(URL)
    print(f"Found {len(products)} products")
    
    if products:
        # Save to database
        save_products(conn, products)
        print(f"Saved {len(products)} products to database")
        
        # Display saved products
        cursor = conn.cursor()
        cursor.execute("SELECT name, url, price FROM products")
        print("\nProducts:")
        for name, url, price in cursor.fetchall():
            print(f"  - {name}")
            if url:
                print(f"    URL: {url}")
            if price:
                print(f"    Price: {price}")
    else:
        print("No products found. The website structure may have changed.")
    
    conn.close()


if __name__ == "__main__":
    main()
