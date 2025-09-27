# eventbrite_scraper_all_events_fixed.py
import time
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://www.eventbrite.ca/d/united-states/events/"
FIELDS = ["title", "date_time", "location", "organizer", "categories", "url", "description"]

def get_event_details(page, url):
    """Open an event page and extract all fields with fallbacks"""
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(2)

        # ---- Title ----
        try:
            title = page.locator("h1").inner_text().strip()
        except:
            title = ""

        # ---- Date & Time ----
        date_time = ""
        selectors_dt = [
            "div[data-testid='event-date-and-time']",
            "time",
            "div[class*='event-details__data']",
            "section:has-text('Date and time')"
        ]
        for sel in selectors_dt:
            try:
                date_time = page.locator(sel).first.inner_text().strip()
                if date_time:
                    break
            except:
                continue

        # ---- Location ----
        location = ""
        selectors_loc = [
            "div[data-testid='event-detail-location']",
            "div[class*='location-info']",
            "section:has-text('Location')",
            "p:has-text('Location')"
        ]
        for sel in selectors_loc:
            try:
                location = page.locator(sel).first.inner_text().strip()
                if location:
                    break
            except:
                continue

        # ---- Organizer ----
        organizer = ""
        selectors_org = [
            "div[data-testid='event-owner-name']",
            "a[href*='/o/']",
            "section:has-text('Organizer')"
        ]
        for sel in selectors_org:
            try:
                organizer = page.locator(sel).first.inner_text().strip()
                if organizer:
                    break
            except:
                continue

        # ---- Categories / Tags ----
        categories = ""
        try:
            tags = page.locator("a[href*='/d/']").all_inner_texts()
            categories = ", ".join([t.strip() for t in tags if t.strip()])
        except:
            categories = ""

        # ---- Description ----
        description = ""
        selectors_desc = [
            "div[data-testid='event-details__content']",     
            "section[data-spec='event-details']",           
            "div[class*='structured-content']",             
            "div[class*='eds-text--break-word']",           
        ]
        for sel in selectors_desc:
            try:
                description = page.locator(sel).first.inner_text().strip()
                if description:
                    break
            except:
                continue

        return {
            "title": title,
            "date_time": date_time,
            "location": location,
            "organizer": organizer,
            "categories": categories,
            "url": url,
            "description": description
        }

    except Exception as e:
        print(f"⚠️ Failed to scrape {url}: {e}")
        return None


def scrape_search_page(page):
    """Collect all event URLs from the current search page"""
    cards = page.locator("a[href*='/e/']")
    n = cards.count()
    print(f"🔎 Found {n} links on this page")
    urls = []

    for i in range(n):
        href = cards.nth(i).get_attribute("href")
        if href and "/e/" in href:
            if href.startswith("/"):
                full_url = "https://www.eventbrite.ca" + href.split("?")[0]
            else:
                full_url = href.split("?")[0]
            urls.append(full_url)   # keep duplicates

    print(f"📌 Collected {len(urls)} links this page (with duplicates)")
    return urls


def main():
    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        search_page = browser.new_page()
        print(f"Opening {URL} ...")
        search_page.goto(URL, wait_until="networkidle", timeout=60000)

        page_num = 1
        while True:
            print(f"\n📄 Scraping search page {page_num}...")
            urls = scrape_search_page(search_page)

            for idx, url in enumerate(urls, start=1):
                print(f"   → Scraping event {len(all_rows)+1}: {url}")

                # ✅ open a new tab for each event
                try:
                    event_page = browser.new_page()
                    details = get_event_details(event_page, url)
                    event_page.close()

                    if details:
                        all_rows.append(details)
                except Exception as e:
                    print(f"⚠️ Failed to scrape {url}: {e}")

            # ---- Pagination ----
            try:
                next_btn = search_page.locator("a[aria-label='Next']")
                if next_btn.is_visible():
                    next_btn.click()
                    search_page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    page_num += 1
                else:
                    print("🚫 No more pages.")
                    break
            except:
                print("🚫 Pagination finished.")
                break

        browser.close()

    # ---- Save results ----
    if all_rows:
        out = Path("eventbrite_all_events_fixed.csv")
        pd.DataFrame(all_rows, columns=FIELDS).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n🎉 Done! Saved {len(all_rows)} events to:", out.resolve())
    else:
        print("⚠️ No events scraped.")


if __name__ == "__main__":
    main()
