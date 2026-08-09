import requests
import os

BASE_URL="https://books.toscrape.com/"
USER_AGENT = "FlyRankInternship-A9/1.0 https://github.com/MahirAhammed/test-scraper.git"
CACHE_DIR = "cache"

def main():
    os.makedirs(CACHE_DIR, exist_ok= True)
    file = f"{CACHE_DIR}/catalogue-page-1.html"
    if os.path.exists(file):
        with open(file, "r", encoding= "utf-8") as f:
            content = f.read()
            print(f"CACHE HIT: {file} ({len(content)} bytes)")
            return

    response = requests.get(BASE_URL, headers= {"User-Agent": USER_AGENT}, timeout= 10)
    if response.status_code != 200:
        print(f"Fetch failed {BASE_URL}: {response.status_code}")
        return

    with open(file, "w", encoding= "utf-8") as f:
        f.write(response.text)

    print(f"FETCH: {file} ({len(response.text)} bytes)")


if __name__ == "__main__":
    main()