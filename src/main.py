import time
from urllib.parse import urljoin
import requests
import os
from bs4 import BeautifulSoup

BASE_URL="https://books.toscrape.com/catalogue/page-1.html"
USER_AGENT = "FlyRankInternship-A9/1.0 (https://github.com/MahirAhammed/test-scraper.git)"
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

    with open(file, "w", encoding= "utf-8") as f:
        f.write(response.text)

    print(f"FETCH: {file} ({len(response.text)} bytes)")
    return response.text, False


def get_book_links(content: str, page_url: str) -> list[str]:
    """
    Extracts all book links from the given HTML content.
    """
    soup = BeautifulSoup(content, "html.parser")
    links = []
    for a in soup.select("article.product_pod h3 a"):
        links.append(urljoin(page_url, a["href"]))

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


def fetch_all_records(limit: int = 3) -> list[str]:
    """
    Fetches and extracts the content of all catalogue pages up to the specified limit.
    """
    current_page = 1
    current_url = BASE_URL
    book_links = []

    while current_url and current_page <= limit:
        filename = f"page-{current_page}.html"
        content, is_cached = fetch_page(current_url, f"catalogue-{filename}")

        if not is_cached:
            time.sleep(0.5)

        book_links.extend(get_book_links(content, current_url))
        current_url = get_next_page_link(content, current_url)
        current_page += 1

    unique_book_links = list(dict.fromkeys(book_links)) # Remove duplicates while preserving order (alternative: set())

    print(f"catalogue_pages={current_page - 1} , discovered= {len(book_links)} , unique_urls={len(unique_book_links)}")
    return unique_book_links
      
def main():
    fetch_all_records(limit= 3)

if __name__ == "__main__":
    main()