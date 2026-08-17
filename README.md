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

## AI vs me

### Prompt
```
Build a Python scraper for `books.toscrape.com`. The scraper only works with the first three catalogue pages of the site, starting at https://books.toscrape.com/catalogue/page-1.html, and moving on to next page using the link within the HTML content. For each page all the URLs of individual books must extracted from the HTML, using the relative links within the page convert them to absolute URLs using `urljoin` function and not string concatenation. For every discovered book, visit its detail page and extract the following:

- title
- product_url (the book's absolute URL)
- price_text (the raw price string shown on the page)
- availability_text (raw stock text)
- rating_text (the start rating as a word, e.g. "Three")
- description (if no description, set to null and no made up text)
- source_page (the catalogue page URL where the book link was found on)
- fetched_at (an ISO 8601 UTC timestamp of when the page was actually fetched)

Normalize the extracted book details into a clean schema with the above fields and following requirements:
- Convert `price_text` into a new numeric field `price_gbp`, while keeping the original alongside
- Validate every record against a valid schema (e.g. with Pydantic), before using it for final output 
- every invalidate record should be set aside into separate `errors.json` file along with reason of failure
- never store duplicate records, based on `product_url`
- write the valid records to `output/books.json`, multiple runs of scraper must always produce 60 records.

Additional requirements:
- Every HTTP request must send an identifying `User-Agent` header naming the scraper and including a contact link (e.g. a GitHub repo URL).
- Every request must have a timeout (a few seconds) so it never hangs indefinitely.
- Wait at least 500ms between real requests to the site, however no delay needed when reading from a local cache.
- Cache every fetched page to disk on first fetch, and read from that cache on subsequent runs instead of re-requesting the same page from the site.
- If a single book page fails to fetch or parse, it must be logged and skipped, the run must continue and still produce all the other valid records.
- On a timeout or 5xx server error, retry the request once after a short wait. Do not retry on a 404 or 403.

Every run should end by writing a `run-report.json` file containing: start time, duration, number of pages freshly fetched, number of cache hits, number of valid records, number of invalid records, and number of failed pages.

```

### What AI did better

- **Cleaner exception handling:** It defines `FetchError` and `ParseError` as distinct exception types, in contrast to reusing a generic `RuntimeError` with string-matching (`"status 5" in str(e)`), making the retry logic's status code branching (404/403 vs 5xx vs timeout) more concise.
- **Stronger schema validation:** The `BookRecord` model have custom field validators to ensure `title` isn't empty, `rating_text` is one of the six known rating words, and `fetched_at` is ISO-parseable. My schema checks fewer of these edge cases.
- **`requests.Session()` reused** across all 63 requests, a minor efficiency improvement (connection reuse).
- **Filure handling for catalogue pages:** If a catalogue page itself fails to fetch or parse, it's logged and the crawl stops gracefully rather than crashing.

### What it wrong wrong or silently ignored

- **No visible progress during the run.** The AI's script has no prints or logs until the very end, when the full `run-report.json` is dumped to console. For the entire run across 63 requests, there's no indication of whether the program still working or hung.
- **`fetched_at` format doesn't match the spec's example.** It uses `.isoformat()` (`...482193+00:00`) instead of the sample's `...T10:00:00Z`.


### What the prompt excluded

- - **No mention of cache file-naming convention.** The naming convention from the assignment brief (`cache/catalogue-page-1.html`) was not mentioned in the prompt, as a result the AI reached for a hashed URL to JSON scheme, which is a reasonable, collision-proof design.
- **No per-request console output specified:** The assignment wants `FETCH`/`CACHE HIT` with byte sizes printed live, and stage summaries such as `catalogue_pages=3, unique_urls=60`. The prompt only described the final report, not the progress feedback expected throughout, which is why there is no indication of any progress made.
- - **No file structure specified:** The prompt does not define a file structure to follow. The AI wrote a single self-contained `scraper.py`, which a completely reasonable choice given no constraint either way, and arguably simpler for a project of this scale (only the base implementation not extras).