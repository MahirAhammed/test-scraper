import requests
import time

def fetch_page_with_retry(fetch_fn, url: str, filename: str, max_retries: int = 3):
    for i in range(max_retries + 1):
        try:
            return fetch_fn(url, filename)
        except requests.exceptions.Timeout as e:
            if i < max_retries:
                time.sleep(1)
                continue
            raise
        except RuntimeError as e:
            if "status 5" in str(e) and i < max_retries:
                time.sleep(1)
                continue
            raise