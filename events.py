import json, random, re, time, datetime
from pathlib import Path
import pandas as pd
from playwright.sync_api import sync_playwright

BASE = "https://visiteurope.com/en"
FIELDS = [
    "title","description",
    "date_start","date_end","time_start","time_end",
    "venue","place","country","price","image","url"
]

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

def consent(page):
    for sel in ["#wzrk-confirm","button:has-text('Accept')","button:has-text('I Agree')","button:has-text('Allow All')"]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=700):
                loc.click(); time.sleep(0.2); return
        except: pass

def scroll_until_stable(page, max_loops=25, pause=0.7):
    """Scroll down until no more new content loads."""
    last = 0; stable = 0
    for _ in range(max_loops):
        page.mouse.wheel(0, 2400)
        time.sleep(pause + random.uniform(0.05, 0.25))
        try: h = page.evaluate("document.body.scrollHeight")
        except: break
        if h == last: stable += 1
        else: stable = 0; last = h
        if stable >= 3: break

def collect_links(page):
    """Collect event links from the /events/ page."""
    links = set()
    try:
        page.wait_for_selector("div[data-testid='event-card'] a", timeout=20000)
    except:
        print("⚠️ No event cards found")
        return []
    loc = page.locator("div[data-testid='event-card'] a")
    n = loc.count()
    for i in range(n):
        try:
            href = loc.nth(i).get_attribute("href")
            if not href: continue
            if href.startswith("/"): href = BASE + href
            href = href.split("?")[0]
            if any(bad in href for bad in ("/privacy","/terms")): continue
            links.add(href)
        except: pass
    return sorted(links)

def first(v):
    if isinstance(v, list) and v: return v[0]
    if isinstance(v, str): return v
    return None

def parse_jsonld_event(obj):
    out = {f: None for f in FIELDS}
    out["title"] = obj.get("name") or obj.get("headline")
    out["description"] = obj.get("description")

    start, end = first(obj.get("startDate")), first(obj.get("endDate"))
    if isinstance(start,str):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})",start)
        if m: out["date_start"],out["time_start"]=m.group(1),m.group(2)
    if isinstance(end,str):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})",end)
        if m: out["date_end"],out["time_end"]=m.group(1),m.group(2)

    loc = obj.get("location")
    if isinstance(loc,dict):
        out["venue"] = first(loc.get("name"))
        addr = loc.get("address") or {}
        out["place"] = addr.get("addressLocality") or addr.get("addressRegion")
        out["country"] = addr.get("addressCountry")

    offers = obj.get("offers")
    if isinstance(offers,dict):
        cur = offers.get("priceCurrency") or ""
        p = offers.get("price")
        if p: out["price"] = f"{cur} {p}"
    elif isinstance(offers,list) and offers:
        cur = offers[0].get("priceCurrency") or ""
        p = offers[0].get("price")
        if p: out["price"] = f"{cur} {p}"

    img = obj.get("image")
    if isinstance(img,str): out["image"] = img
    elif isinstance(img,list) and img: out["image"] = img[0]

    return out

def parse_event(page,url):
    row = {f: None for f in FIELDS}; row["url"]=url
    scripts = page.locator("script[type='application/ld+json']")
    try: n = scripts.count()
    except: n=0
    for i in range(n):
        try:
            data = scripts.nth(i).inner_text()
            if not data: continue
            data = json.loads(data)
        except: continue
        items = data if isinstance(data,list) else [data]
        for it in items:
            if isinstance(it,dict):
                t=it.get("@type")
                if t=="Event" or (isinstance(t,list) and "Event" in t):
                    got=parse_jsonld_event(it)
                    for k,v in got.items():
                        if v and not row[k]: row[k]=v
        if row["title"]: break
    if not row["title"]:
        try: row["title"]=(page.title() or "").strip() or None
        except: pass
    return row

def retry_goto(page,url,attempts=3,wait="domcontentloaded",timeout=60000):
    last=None
    for i in range(attempts):
        try:
            page.goto(url,wait_until=wait,timeout=timeout)
            return True,None
        except Exception as e:
            last=e; time.sleep(1.2+i*0.8+random.uniform(0.2,0.6))
    return False,last

def main():
    ua=random.choice(UAS); rows=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)  # set True for background run
        ctx=browser.new_context(
            locale="en-GB",
            timezone_id="Europe/Berlin",
            user_agent=ua,
            viewport={"width":random.randint(1280,1600),"height":random.randint(800,1000)},
        )
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page=ctx.new_page()

        url=f"{BASE}/events/"
        print(f"🔎 Scraping: {url}")
        ok,err=retry_goto(page,url)
        consent(page); time.sleep(3)
        if not ok: 
            print("[warn] nav failed:",err); return

        scroll_until_stable(page)
        time.sleep(5)

        links=collect_links(page)
        print(f"Found {len(links)} event links")

        for i,link in enumerate(links,1):
            print(f"[{i}/{len(links)}] {link}")
            ok,err=retry_goto(page,link)
            consent(page); time.sleep(0.5)
            if not ok: print(" -> skip",err); continue
            data=parse_event(page,link)
            rows.append(data); time.sleep(0.3)

        ctx.close(); browser.close()

    timestamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out=Path(f"visiteurope_events_{timestamp}.csv")
    pd.DataFrame(rows,columns=FIELDS).to_csv(out,index=False,encoding="utf-8-sig")
    print("✅ Saved:", out.resolve())

if __name__=="__main__":
    main()
