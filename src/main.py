import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
import os
from bs4 import BeautifulSoup
from validate import validate_records, write_output
from retry import fetch_page_with_retry
from report import write_run_report

BASE_URL="https://books.toscrape.com/catalogue/page-1.html"
USER_AGENT = "FlyRankInternship-A9/1.0 (+https://github.com/MahirAhammed/test-scraper.git)"
CACHE_DIR = "cache"

def fetch_page(url: str, filename: str) -> tuple[str, bool]:
    """
    Fetches a page from the given URL and caches it locally, or returns the cached version.
    """
    os.makedirs(CACHE_DIR, exist_ok= True)
    file = f"{CACHE_DIR}/{filename}"

    if os.path.exists(file):
        with open(file, "r", encoding= "utf-8") as f:
            content = f.read()
        print(f"CACHE HIT: {file} ({len(content)} bytes)")
        return content, True

    response = requests.get(url, headers= {"User-Agent": USER_AGENT}, timeout= 10)
    if response.status_code != 200:
        raise RuntimeError(f"Fetch failed {url}: status {response.status_code}")

    response.encoding = "utf-8"
    with open(file, "w", encoding= "utf-8") as f:
        f.write(response.text)

    print(f"FETCH: {file} ({len(response.text)} bytes)")
    time.sleep(0.5)
    return response.text, False


def get_book_links(content: str, page_url: str) -> list[tuple[str, str]]:
    """
    Extracts all book links from the given HTML content.
    """
    soup = BeautifulSoup(content, "html.parser")
    links = []
    for a in soup.select("article.product_pod h3 a"):
        links.append((urljoin(page_url, a["href"]), page_url))
    return links


def get_next_page_link(content: str, page_url: str) -> str | None:
    """
    Extracts the link to the next page from the given HTML content.
    """
    soup = BeautifulSoup(content, "html.parser")
    next_page = soup.select_one("li.next a")
    if next_page and next_page.get("href"):
        return urljoin(page_url, next_page["href"])
    return None


def fetch_all_records(limit: int = 3) -> tuple[list[tuple[str, str]], int, int]:
    """
    Fetches and extracts the content of all catalogue pages up to the specified limit.
    """
    current_page = 1
    current_url = BASE_URL
    book_links = []
    pages_fetched = 0
    cache_hits = 0

    while current_url and current_page <= limit:
        filename = f"page-{current_page}.html"
        content, is_cached = fetch_page_with_retry(fetch_page, current_url, f"catalogue-{filename}")

        if is_cached: 
            cache_hits += 1
        else:
            pages_fetched += 1

        book_links.extend(get_book_links(content, current_url))
        current_url = get_next_page_link(content, current_url)
        current_page += 1

    unique_book_links = list(dict.fromkeys(book_links)) # Remove duplicates while preserving order (alternative: set())

    print(f"catalogue_pages={current_page - 1} , discovered= {len(book_links)} , unique_urls={len(unique_book_links)}")
    return unique_book_links, pages_fetched, cache_hits


def fetch_all_books(book_urls: list[tuple[str, str]]) -> tuple[list[dict], list[dict], int, int]:
    """
    Fetches and extracts the content of all book pages from the given list of URLs.
    """
    records = []
    failed_urls = []
    pages_fetched = 0
    cache_hits = 0

    for url, source_page in book_urls:
        filename = urlparse(url).path.rsplit("/")[-2] + ".html"
        try:
            content, is_cached = fetch_page_with_retry(fetch_page, url, f"book-{filename}")

        except Exception as e:
            failed_urls.append({"url": url, "reason": str(e)})
            continue

        if is_cached:
            cache_hits += 1
        else:
            pages_fetched += 1

        fetched_at = datetime.fromtimestamp(os.path.getmtime(f"{CACHE_DIR}/book-{filename}"), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        records.append(extract_book_details(content, url, source_page, fetched_at))

    print(records[0])
    print(f"detail_pages={len(book_urls)}")
    return records, failed_urls, pages_fetched, cache_hits


def extract_book_details(content: str, url: str, source_page: str, fetched_at: str) -> dict:
    """
    Extracts the details of a book from the given HTML content."""
    soup = BeautifulSoup(content, "html.parser")
    product = soup.select_one("div.product_main")
    title = product.select_one("h1").text.strip()
    price_text = product.select_one("p.price_color").text.strip()
    available_text = product.select_one("p.availability").text.strip()
    rating_text = product.select_one("p.star-rating")["class"][1]

    description = None
    has_description = soup.select_one("#product_description")
    if has_description and has_description.find_next_sibling("p"):
        description = has_description.find_next_sibling("p").text.strip()

    return {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "availability_text": available_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }


def main():
    start_time = datetime.now(timezone.utc)

    books, catalogue_fetched, catalogue_hits = fetch_all_records(limit= 3)

    # Failed page test (Stage 5) -- uncomment line below to test
    # books.append(("https://books.toscrape.com/catalogue/not-a-real-book_9999/index.html", BASE_URL))

    raw_records, failed_pages, pages_fetched, cache_hits = fetch_all_books(books)

    valid, invalid = validate_records(raw_records)
    print(f"valid_records={len(valid)} , invalid_records={len(invalid)}")

    write_output(valid, invalid)
    write_run_report(
        start_time, 
        catalogue_fetched + pages_fetched, 
        catalogue_hits + cache_hits, 
        valid_count=len(valid), 
        invalid_count=len(invalid),
        failed_pages=failed_pages
    )

if __name__ == "__main__":
    main()