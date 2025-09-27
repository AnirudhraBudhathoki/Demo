# eventbrite_event_pages_incremental.py
import time
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.eventbrite.ca/d/united-states/events/"
FIELDS = ["title", "date_time", "location", "price", "url"]

def safe_get_text(page, selectors):
    """Try multiple selectors, return first non-empty text"""
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                txt = page.locator(sel).first.inner_text().strip()
                if txt:
                    return txt
        except:
            continue
    return ""

def get_event_details(page, url):
    """Open an event page and extract details"""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # Title
        title = safe_get_text(page, ["h1", "div[class*='event-title']"])

        # Date/time
        date_time = safe_get_text(page, [
            "div[data-testid='event-date-and-time']",
            "section[aria-label='Date and time']",
            "div[class*='event-details__data']"
        ])

        # Location
        location = safe_get_text(page, [
            "div[data-testid='event-detail-location']",
            "section[aria-label='Location']",
            "div[class*='event-details__data']"
        ])

        # Price
        price = safe_get_text(page, [
            "div[data-testid='event-details__data']",
            "section[aria-label='Refund Policy']",
            "div[class*='ticket-price']",
            "span[class*='price']"
        ])

        return {
            "title": title,
            "date_time": date_time,
            "location": location,
            "price": price,
            "url": url
        }

    except Exception as e:
        print(f"⚠️ Failed to scrape {url}: {e}")
        return None

def save_partial(all_rows, filename="eventbrite_events_partial.csv"):
    """Save progress incrementally"""
    df = pd.DataFrame(all_rows, columns=FIELDS)
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"💾 Progress saved: {len(all_rows)} events into {filename}")

def main():
    all_rows = []
    seen_urls = set()
    out_final = Path("eventbrite_all_events.csv")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Opening {URL} ...")
        page.goto(URL, wait_until="networkidle", timeout=60000)

        page_num = 1
        while True:
            print(f"\n📄 Scraping search page {page_num}...")
            # Collect all event links from current page
            cards = page.locator("a[href*='/e/']")
            n = cards.count()
            urls = set()
            for i in range(n):
                href = cards.nth(i).get_attribute("href")
                if href and "/e/" in href:
                    if href.startswith("/"):
                        full_url = "https://www.eventbrite.ca" + href.split("?")[0]
                    else:
                        full_url = href.split("?")[0]
                    urls.add(full_url)

            print(f"🔎 Found {len(urls)} unique events on this page")

            # Scrape each event
            for url in urls:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                print(f"   → Scraping event {len(seen_urls)}: {url}")
                details = get_event_details(page, url)
                if details:
                    all_rows.append(details)

                # Save incrementally every 10 events
                if len(all_rows) % 10 == 0:
                    save_partial(all_rows)

            # Try pagination (Next button)
            try:
                next_btn = page.locator("a[aria-label='Next']")
                if next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    page_num += 1
                else:
                    print("🚫 No more pages.")
                    break
            except:
                print("🚫 Pagination finished.")
                break

        browser.close()

    # Final save
    if all_rows:
        out = Path("eventbrite_event1_pages.csv")

        pd.DataFrame(all_rows, columns=FIELDS).to_csv(out_final, index=False, encoding="utf-8-sig")
        print(f"\n🎉 Done! Saved {len(all_rows)} events to:", out_final.resolve())
    else:
        print("⚠️ No events scraped.")

if __name__ == "__main__":
    main()
