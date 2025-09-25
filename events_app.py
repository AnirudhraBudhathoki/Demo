# visiteurope_destinations.py
import argparse, json, os, random, time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

BASE = "https://visiteurope.com"
START_URL = f"{BASE}/en/destinations/"
FIELDS = ["title", "description", "url"]

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

def retry_goto(page, url, attempts=3, wait="domcontentloaded", timeout=60000):
    last = None
    for i in range(attempts):
        try:
            page.goto(url, wait_until=wait, timeout=timeout)
            return True, None
        except Exception as e:
            last = e
            time.sleep(1 + i * 0.8 + random.uniform(0.2, 0.5))
    return False, last

def scroll_until_stable(page, max_loops=15, pause=0.6):
    last = 0
    stable = 0
    for _ in range(max_loops):
        page.mouse.wheel(0, 2500)
        time.sleep(pause + random.uniform(0.05, 0.25))
        h = page.evaluate("document.body.scrollHeight")
        if h == last:
            stable += 1
            if stable >= 3:
                break
        else:
            last = h
            stable = 0

def collect_links(page):
    links = set()
    # Destination cards are <a href="/en/destination/...">
    loc = page.locator("a[href*='/en/destination/']")
    try:
        n = loc.count()
    except:
        n = 0
    for i in range(n):
        try:
            href = loc.nth(i).get_attribute("href")
            if not href: 
                continue
            if href.startswith("/"): 
                href = BASE + href
            links.add(href.split("?")[0])
        except:
            pass
    return sorted(links)

def parse_destination(page, url):
    row = {"title": None, "description": None, "url": url}
    try:
        row["title"] = (page.locator("h1").inner_text() or "").strip()
    except:
        pass
    try:
        desc = page.locator("meta[name='description']").get_attribute("content")
        if not desc:
            desc = page.locator("p").first.inner_text()
        row["description"] = desc.strip() if desc else None
    except:
        pass
    return row

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--headless", type=int, default=1)
    ap.add_argument("--out", default="destinations.csv")
    args = ap.parse_args()

    rows = []
    ua = random.choice(UAS)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(args.headless))
        ctx = browser.new_context(user_agent=ua)
        page = ctx.new_page()

        ok, err = retry_goto(page, START_URL)
        if not ok:
            print("[error] cannot open start page:", err)
            return

        scroll_until_stable(page)

        links = collect_links(page)
        print(f"Found {len(links)} destinations")

        for i, url in enumerate(links[: args.limit], 1):
            print(f"[{i}/{min(len(links), args.limit)}] {url}")
            ok, err = retry_goto(page, url)
            if not ok:
                print("  -> skip (nav failed):", err)
                continue
            data = parse_destination(page, url)
            rows.append(data)
            time.sleep(0.3 + random.uniform(0.05, 0.25))

        ctx.close()
        browser.close()

    out = Path(args.out)
    tmp = out.with_suffix(".tmp")
    pd.DataFrame(rows, columns=FIELDS).to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, out)
    print("Saved:", out.resolve())

if __name__ == "__main__":
    main()
