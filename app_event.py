# app_event.py
import time, random, os
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://visiteurope.com/en/events/explore/cultural-events"
FIELDS = ["title","short_description","date","place","country","url"]

def scroll_until_stable(page, max_loops=15, pause=0.7):
    """Scroll page until no new content is loaded"""
    last = 0
    stable = 0
    for _ in range(max_loops):
        try:
            page.mouse.wheel(0, 2500)
            time.sleep(pause + random.uniform(0.05, 0.25))
            h = page.evaluate("document.body.scrollHeight")
        except Exception as e:
            print("[warn] scroll skipped:", e)
            break
        if h == last:
            stable += 1
            if stable >= 3:
                break
        else:
            last = h
            stable = 0

def collect_event_cards(page):
    rows = []
    cards = page.locator("div.event-card")  # each event card
    n = cards.count()
    print(f"Found {n} event cards")
    for i in range(n):
        try:
            card = cards.nth(i)
            href = card.locator("a").get_attribute("href")
            if href and href.startswith("/"):
                href = "https://visiteurope.com" + href
            title = card.locator("h3").inner_text().strip()
            desc = card.locator("p").first.inner_text().strip()
            date = card.locator(".event-card__date").inner_text().strip()
            place = card.locator(".event-card__location").inner_text().strip()
            country = place.split(",")[-1].strip() if "," in place else None
            rows.append({
                "title": title,
                "short_description": desc,
                "date": date,
                "place": place,
                "country": country,
                "url": href
            })
        except Exception as e:
            print("skip card:", e)
    return rows

def main():
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Opening {URL} ...")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        # wait until event cards are present
        try:
            page.wait_for_selector("div.event-card", timeout=20000)
        except:
            print("⚠️ No event cards found on page load")
            browser.close()
            return

        scroll_until_stable(page)

        cards = collect_event_cards(page)
        print(f"Total events collected: {len(cards)}")

        rows.extend(cards)
        browser.close()

    # save CSV safely
    out = Path("events1.csv")
    tmp = out.with_suffix(".tmp")
    pd.DataFrame(rows, columns=FIELDS).to_csv(tmp, index=False, encoding="utf-8-sig")
    try:
        os.replace(tmp, out)
        print("Saved:", out.resolve())
    except PermissionError:
        alt = out.with_name(f"{out.stem}_{int(time.time())}{out.suffix}")
        os.replace(tmp, alt)
        print(f"[warn] file locked, saved as:", alt.resolve())

if __name__ == "__main__":
    main()
