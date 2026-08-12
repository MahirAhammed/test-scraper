import json
from datetime import datetime, timezone

def write_run_report(start_time, pages_fetched, cache_hits, valid_count, invalid_count, failed_pages):
    """
    Writes a run report to a JSON file.
    """
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    report = {
        "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": round(duration, 2),
        "pages_fetched": pages_fetched,
        "cache_hits": cache_hits,
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "failed_pages": len(failed_pages),
        "failed_page_details": failed_pages
    }

    with open("output/run-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"failed_pages={len(failed_pages)}")