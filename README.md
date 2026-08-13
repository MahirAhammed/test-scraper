# Test-Scraper

A simple test web scraping pipeline fetching the first 3 catalogue pages of `Books to Scrap` site, visiting book pages to produce clean, validated JSON.

## Target Classification
- **Site:** https://books.toscrape.com/
- **Why:** It's a public sandbox explicitly built for practicing web scraping.
- **Scope:** The first 3 catalogue pages (~60 books).
- **Data collected:** Title, price, availability, star rating, description and product URL.
- **Why this is appropriate:** The site exists for the purpose to test web scraping mentioned explicitly, and requires no login.
- **`robots.txt` request:** no robots file found

I will not reuse this code on another site without checking its rules and terms first.

## Setup and run

- **Lane:** Python 3.12 

```bash
git clone https://github.com/MahirAhammed/test-scraper.git
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- Run the program:
```bash
python src/main.py
```

## Record schema


| Field               | Type          |
|---------------------|---------------|
| `title`             | string  |
| `product_url`       | string (URL)  |
| `price_text`        | string  |
| `price_gbp`         | float |
| `availability_text` | string  |
| `rating_text`       | string  |
| `description`       | string / null  |
| `source_page`       | string (URL)  | 
| `fetched_at`        | string (ISO)  |

## Politeness rules

- **User-agent:** `FlyRankInternship-A9/1.0 (+https://github.com/MahirAhammed/test-scraper.git)`
  - to identify the requests as a student project with a link back to the repo.
- **Timeout:** every request gives up after 10 seconds.
- **Delay:** 0.5s between real requests to the site; cached pages need no delay.
- **Cache:** every page is saved to `cache/` on first fetch, reruns during development read from disk instead of hitting the site again.
- **Retry:** one retry on timeout or 5xx server errors, 404 and 403 are never retried.

## Limitation
- Cache never expires or auto-invalidates, if fetch logic changes, cache/ must be manually deleted to avoid serving stale data.

## Sample run report

```json
{
  "start_time": "2026-08-12T20:35:44Z",
  "duration_seconds": 120.53,
  "pages_fetched": 63,
  "cache_hits": 0,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 1
}
```

- The book data needed for the project is already present in the raw HTML the server sends on first response. A browser would only add cost (memory, startup time, JS execution) without retrieving any additional data.

## Ethics note
- This scraper only targets a sandbox built explicitly for practicing scraping. In general, before scraping any real site the following must be followed: check for an official API first and prefer it over scraping, read `robots.txt` and the site's terms of service and respect what they document, never bypass a login wall, paywall, CAPTCHA, or IP block, and only collect the specific data needed for the task, reachable does not entail permission.