import requests
from bs4 import BeautifulSoup
import sqlite3
from urllib.parse import urljoin

URL =  "https://midiltd.ru/catalog/napolnye_pokrytiya/filter/in_stock-is-y/apply/?SHOWALL_1=1"
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

    # Navigation items to filter out
    skip_names = {"главная", "каталог", "напольные покрытия", "корзина", "контакты"}

    # Try common e-commerce patterns for product titles
    selectors = [
        ".catalog-table__info-title",
        ".product-item .name",
        ".product-item .title",
        ".product-title",
        ".product-name",
        ".catalog-item .name",
        ".catalog-item .title",
        "[itemprop='name']",
        ".item-title",
        ".product-card .name"
    ]

    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            for elem in elements:
                name = elem.get_text(strip=True)
                if name and name.lower() not in skip_names:
                    # Try to find product link
                    link_elem = elem.find("a")
                    product_url = None
                    if link_elem:
                        product_url = urljoin(url, link_elem.get("href", ""))
                    
                    # Find price: go up to .catalog-item and find .price__new-val
                    price = None
                    catalog_item = elem.find_parent(class_="catalog-item")
                    if catalog_item:
                        price_elem = catalog_item.select_one(".price__new-val")
                        if price_elem:
                            price = price_elem.get_text(strip=True)
                    
                    products.append((name, product_url, price))
            break  # Found products with this selector, stop trying others

    return products


def save_products(conn, products):
    """Save products to the database."""
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO products (name, url, price) VALUES (?, ?, ?)",
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
