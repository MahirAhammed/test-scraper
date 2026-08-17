#!/usr/bin/env python3
"""
Scraper for books.toscrape.com (catalogue pages 1-3).

Usage:
    python3 scraper.py

Outputs (relative to CWD):
    output/books.json        -- valid, deduplicated, schema-validated records
    output/errors.json       -- records/pages that failed fetch/parse/validation, with reasons
    output/run-report.json   -- summary stats for the run
    cache/                   -- on-disk HTML cache (used on subsequent runs)

Design notes:
    - Every HTTP request carries an identifying User-Agent with a contact link.
    - Every request has a short timeout, and a single retry (after a short
      backoff) is attempted on timeout or 5xx responses. 404/403 are not retried.
    - A minimum delay is enforced between *real* (non-cached) network requests.
    - Every fetched page is cached to disk; subsequent runs read from the
      cache instead of re-requesting the same URL, so results (and record
      counts) are stable across runs.
    - Final records are deduplicated by product_url and validated against a
      Pydantic schema before being written out.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError, field_validator

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

START_URL = "https://books.toscrape.com/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

CACHE_DIR = "cache"
OUTPUT_DIR = "output"

REQUEST_TIMEOUT = 6  # seconds
MIN_DELAY_BETWEEN_REAL_REQUESTS = 0.5  # seconds
RETRY_WAIT = 1.5  # seconds, before the single retry attempt

USER_AGENT = (
    "BooksToScrapeSampleBot/1.0 "
    "(+https://github.com/anthropics/books-toscrape-scraper; contact via GitHub issues)"
)

VALID_RATING_WORDS = {"Zero", "One", "Two", "Three", "Four", "Five"}


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class FetchError(Exception):
    """Raised when a page cannot be fetched (after retry where applicable)."""


class ParseError(Exception):
    """Raised when a fetched page's HTML doesn't contain what we expect."""


# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------


class BookRecord(BaseModel):
    title: str
    product_url: str
    price_text: str
    price_gbp: float
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: str
    fetched_at: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title is empty")
        return v

    @field_validator("product_url", "source_page")
    @classmethod
    def must_be_http_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"not an absolute http(s) URL: {v!r}")
        return v

    @field_validator("rating_text")
    @classmethod
    def rating_must_be_known_word(cls, v: str) -> str:
        if v not in VALID_RATING_WORDS:
            raise ValueError(f"unrecognized rating word: {v!r}")
        return v

    @field_validator("price_gbp")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(f"price_gbp must be positive, got {v}")
        return v

    @field_validator("fetched_at")
    @classmethod
    def fetched_at_must_be_iso(cls, v: str) -> str:
        # Raises ValueError itself if not parseable, which is what we want.
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------


@dataclass
class RunStats:
    pages_fetched_fresh: int = 0
    cache_hits: int = 0
    failed_pages: int = 0
    invalid_records: int = 0
    valid_records: int = 0
    error_log: list = field(default_factory=list)


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------


def _cache_path(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_DIR, f"{digest}.json")


def _load_from_cache(url: str) -> Optional[dict]:
    path = _cache_path(url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_to_cache(url: str, html: str, fetched_at: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(url)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"url": url, "html": html, "fetched_at": fetched_at}, f)


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------


def fetch(url: str, session: requests.Session, stats: RunStats) -> tuple[str, str]:
    """
    Return (html, fetched_at) for `url`.

    Serves from the on-disk cache when available. Otherwise performs a real
    HTTP GET with a timeout and identifying User-Agent, retrying once (after
    a short wait) on timeout or 5xx response. 404/403 are not retried.
    """
    cached = _load_from_cache(url)
    if cached is not None:
        stats.cache_hits += 1
        return cached["html"], cached["fetched_at"]

    headers = {"User-Agent": USER_AGENT}
    attempts_made = 0
    last_exc: Optional[Exception] = None

    while attempts_made < 2:
        attempts_made += 1
        try:
            resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            if attempts_made < 2:
                time.sleep(RETRY_WAIT)
                continue
            raise FetchError(f"timed out after retry: {url}") from exc
        except requests.exceptions.RequestException as exc:
            raise FetchError(f"request failed for {url}: {exc}") from exc

        if resp.status_code in (404, 403):
            raise FetchError(f"HTTP {resp.status_code} for {url} (not retried)")

        if 500 <= resp.status_code < 600:
            last_exc = FetchError(f"HTTP {resp.status_code} for {url}")
            if attempts_made < 2:
                time.sleep(RETRY_WAIT)
                continue
            raise last_exc

        if resp.status_code != 200:
            raise FetchError(f"HTTP {resp.status_code} for {url}")

        # Success.
        fetched_at = datetime.now(timezone.utc).isoformat()
        _save_to_cache(url, resp.text, fetched_at)
        stats.pages_fetched_fresh += 1
        time.sleep(MIN_DELAY_BETWEEN_REAL_REQUESTS)
        return resp.text, fetched_at

    # Should not be reachable, but keep mypy/pylint happy.
    raise FetchError(f"failed to fetch {url}: {last_exc}")


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def parse_catalogue_page(html: str, page_url: str) -> tuple[list[str], Optional[str]]:
    """Return (absolute book URLs on this page, absolute URL of next page or None)."""
    soup = BeautifulSoup(html, "html.parser")

    book_urls = []
    for a in soup.select("article.product_pod h3 a"):
        href = a.get("href")
        if not href:
            continue
        book_urls.append(urljoin(page_url, href))

    next_url = None
    next_a = soup.select_one("li.next a")
    if next_a and next_a.get("href"):
        next_url = urljoin(page_url, next_a["href"])

    return book_urls, next_url


def parse_book_page(html: str, product_url: str, source_page: str, fetched_at: str) -> dict:
    """Extract raw (pre-validation) fields from a book detail page."""
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("div.product_main h1")
    if not title_el:
        raise ParseError("missing title element (div.product_main h1)")
    title = title_el.get_text(strip=True)

    price_el = soup.select_one("div.product_main p.price_color")
    if not price_el:
        raise ParseError("missing price element (p.price_color)")
    price_text = price_el.get_text(strip=True)

    availability_el = soup.select_one("p.availability")
    if not availability_el:
        raise ParseError("missing availability element (p.availability)")
    availability_text = " ".join(availability_el.get_text().split())

    rating_el = soup.select_one("p.star-rating")
    if not rating_el:
        raise ParseError("missing rating element (p.star-rating)")
    rating_classes = [c for c in rating_el.get("class", []) if c != "star-rating"]
    rating_text = rating_classes[0] if rating_classes else ""

    description = None
    desc_heading = soup.select_one("#product_description")
    if desc_heading:
        desc_p = desc_heading.find_next_sibling("p")
        if desc_p:
            desc_text = desc_p.get_text(strip=True)
            description = desc_text if desc_text else None

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at,
    }


def price_text_to_gbp(price_text: str) -> float:
    """Extract a numeric GBP amount from a raw price string like '£51.77'."""
    match = re.search(r"(\d+\.\d+|\d+)", price_text)
    if not match:
        raise ValueError(f"could not parse a number out of price_text {price_text!r}")
    return float(match.group(1))


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def build_and_validate(raw: dict) -> tuple[Optional[dict], Optional[str]]:
    """
    Attempt to compute price_gbp and validate `raw` against BookRecord.

    Returns (validated_dict, None) on success, or (None, reason) on failure.
    """
    try:
        price_gbp = price_text_to_gbp(raw["price_text"])
    except ValueError as exc:
        return None, f"price parsing failed: {exc}"

    candidate = dict(raw)
    candidate["price_gbp"] = price_gbp

    try:
        record = BookRecord(**candidate)
    except ValidationError as exc:
        reasons = "; ".join(f"{e['loc']}: {e['msg']}" for e in exc.errors())
        return None, f"schema validation failed: {reasons}"

    return record.model_dump(), None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def run() -> None:
    start_time = datetime.now(timezone.utc)
    session = requests.Session()
    stats = RunStats()

    # --- Step 1: walk catalogue pages 1..3, following the "next" link ---
    book_entries: dict[str, str] = {}  # product_url -> source_page (first occurrence wins)
    current_url: Optional[str] = START_URL
    pages_visited = 0

    while current_url and pages_visited < MAX_CATALOGUE_PAGES:
        pages_visited += 1
        try:
            html, _fetched_at = fetch(current_url, session, stats)
        except FetchError as exc:
            stats.failed_pages += 1
            stats.error_log.append(
                {"url": current_url, "stage": "fetch_catalogue", "reason": str(exc)}
            )
            break

        try:
            book_urls, next_url = parse_catalogue_page(html, current_url)
        except Exception as exc:  # noqa: BLE001 - log and stop walking on catalogue parse failure
            stats.failed_pages += 1
            stats.error_log.append(
                {"url": current_url, "stage": "parse_catalogue", "reason": str(exc)}
            )
            break

        for book_url in book_urls:
            if book_url not in book_entries:
                book_entries[book_url] = current_url

        current_url = next_url

    # --- Step 2: visit each book detail page ---
    valid_records: dict[str, dict] = {}  # keyed by product_url for de-dup

    for book_url, source_page in book_entries.items():
        try:
            html, fetched_at = fetch(book_url, session, stats)
        except FetchError as exc:
            stats.failed_pages += 1
            stats.error_log.append(
                {"url": book_url, "source_page": source_page, "stage": "fetch_book", "reason": str(exc)}
            )
            continue

        try:
            raw = parse_book_page(html, book_url, source_page, fetched_at)
        except ParseError as exc:
            stats.failed_pages += 1
            stats.error_log.append(
                {"url": book_url, "source_page": source_page, "stage": "parse_book", "reason": str(exc)}
            )
            continue

        record, reason = build_and_validate(raw)
        if record is None:
            stats.invalid_records += 1
            stats.error_log.append(
                {"url": book_url, "source_page": source_page, "stage": "validation", "reason": reason}
            )
            continue

        product_url = record["product_url"]
        if product_url in valid_records:
            continue  # duplicate, skip silently
        valid_records[product_url] = record

    stats.valid_records = len(valid_records)

    # --- Step 3: write outputs ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, "books.json"), "w", encoding="utf-8") as f:
        json.dump(list(valid_records.values()), f, indent=2, ensure_ascii=False)

    with open(os.path.join(OUTPUT_DIR, "errors.json"), "w", encoding="utf-8") as f:
        json.dump(stats.error_log, f, indent=2, ensure_ascii=False)

    end_time = datetime.now(timezone.utc)
    report = {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": (end_time - start_time).total_seconds(),
        "pages_freshly_fetched": stats.pages_fetched_fresh,
        "cache_hits": stats.cache_hits,
        "valid_records": stats.valid_records,
        "invalid_records": stats.invalid_records,
        "failed_pages": stats.failed_pages,
    }
    with open(os.path.join(OUTPUT_DIR, "run-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
