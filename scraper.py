"""
Scrape the Books to Scrape catalogue for Data Science 500.
Usage from project root: python src/scraper.py
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
HEADERS = {"User-Agent": "StudentDataScienceProject/1.0 (educational scraping)"}
RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_stock(text: str) -> tuple[str, int | None]:
    """Return stock status and quantity when the page provides it."""
    text = " ".join(text.split())
    quantity_match = re.search(r"\((\d+)\s+available\)", text, flags=re.I)
    quantity = int(quantity_match.group(1)) if quantity_match else None
    if "in stock" in text.lower():
        return "In stock", quantity
    if "out of stock" in text.lower():
        return "Out of stock", quantity
    return "Unknown", quantity


def scrape_catalogue(max_pages: int | None = None, delay: float = 0.05) -> pd.DataFrame:
    """Follow catalogue pagination and scrape each listing page."""
    session = requests.Session()
    session.headers.update(HEADERS)
    url = BASE_URL
    rows = []
    page_count = 0

    while url:
        page_count += 1
        if max_pages is not None and page_count > max_pages:
            break
        response = session.get(url, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for book in soup.select("article.product_pod"):
            title_node = book.select_one("h3 a")
            price_node = book.select_one(".price_color")
            rating_node = book.select_one("p.star-rating")
            availability_node = book.select_one(".availability")

            title = title_node.get("title", title_node.get_text(strip=True)) if title_node else None
            price_text = price_node.get_text(strip=True) if price_node else ""
            # Site prices are displayed in GBP, e.g. £51.77.
            price_match = re.search(r"[\d.]+", price_text.replace(",", ""))
            price_gbp = float(price_match.group()) if price_match else None
            rating_word = None
            if rating_node:
                classes = rating_node.get("class", [])
                rating_word = next((c for c in classes if c in RATING_MAP), None)
            stock_text = availability_node.get_text(" ", strip=True) if availability_node else ""
            stock_status, stock_quantity = parse_stock(stock_text)
            product_href = title_node.get("href") if title_node else None
            product_url = urljoin(url, product_href) if product_href else None

            rows.append({
                "title": title,
                "price_gbp": price_gbp,
                "rating_word": rating_word,
                "rating": RATING_MAP.get(rating_word),
                "stock_status": stock_status,
                "stock_quantity": stock_quantity,
                "product_url": product_url,
            })

        next_node = soup.select_one("li.next a")
        url = urljoin(url, next_node.get("href")) if next_node else None
        if delay:
            time.sleep(delay)

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("No books were scraped. Check your internet connection or the website structure.")
    return df


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardise the scraped dataset."""
    clean = df.copy()
    clean["title"] = clean["title"].astype("string").str.strip()
    clean["price_gbp"] = pd.to_numeric(clean["price_gbp"], errors="coerce")
    clean["rating"] = pd.to_numeric(clean["rating"], errors="coerce")
    clean["stock_quantity"] = pd.to_numeric(clean["stock_quantity"], errors="coerce")
    clean["rating_word"] = clean["rating_word"].astype("string").str.strip()
    clean["stock_status"] = clean["stock_status"].fillna("Unknown").astype(str).str.strip()
    clean = clean.drop_duplicates(subset=["title", "product_url"])
    clean = clean.dropna(subset=["title", "price_gbp"])
    clean = clean[clean["price_gbp"] >= 0]
    clean["stock_available"] = (clean["stock_status"] == "In stock").astype(int)
    clean["rating"] = clean["rating"].astype("Int64")
    clean["stock_quantity"] = clean["stock_quantity"].astype("Int64")
    return clean.reset_index(drop=True)


def main():
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    data_dir.mkdir(exist_ok=True)
    print("Scraping Books to Scrape catalogue...")
    raw = scrape_catalogue()
    clean = clean_dataset(raw)
    output = data_dir / "books_dataset.csv"
    clean.to_csv(output, index=False)
    print(f"Scraped {len(raw)} listings; saved {len(clean)} cleaned books to {output}")


if __name__ == "__main__":
    main()
