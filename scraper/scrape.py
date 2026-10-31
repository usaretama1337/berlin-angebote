"""Собирает акции REWE, EDEKA и ALDI Nord и сохраняет их в site/offers.json.

Как это работает: для каждого магазина открывается настоящий браузер
(Chromium через Playwright), страница с акциями прокручивается до конца,
а сборщик ищет товары тремя способами:
  1. в данных, которые страница сама загружает с сервера магазина (JSON);
  2. в данных, встроенных в HTML (__NEXT_DATA__, ld+json и т. п.);
  3. в самих карточках товаров на странице, если первые два ничего не дали.
Так сборщику не нужно знать точное устройство каждого сайта, и он меньше
ломается, когда магазин меняет дизайн.

Если магазин не удалось собрать, на сайте остаются его прошлые акции,
а в папку debug/ сохраняются HTML, скриншот и найденные данные для разбора.
"""
import asyncio
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from categories import categorize, categories_for_site
from config import HEADLESS, MIN_OFFERS, STORES

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "site" / "offers.json"
DEBUG_DIR = ROOT / "debug"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

NAME_KEYS = ("title", "name", "productName", "headline", "productTitle",
             "displayName", "articleName", "nameShort")
PRICE_KEYS = ("price", "currentPrice", "offerPrice", "salesPrice", "salePrice",
              "priceValue", "priceAmount", "discountPrice", "promotionPrice",
              "priceInCents", "currentRetailPrice")
OLD_KEYS = ("regularPrice", "oldPrice", "originalPrice", "strikePrice",
            "strikeThroughPrice", "listPrice", "previousPrice", "crossedOutPrice",
            "regularPriceInCents", "referencePrice", "uvp")
IMG_KEYS = ("image", "imageUrl", "imageURL", "img", "picture", "images", "media",
            "thumbnail", "primaryImage", "productImage", "assets")
UNIT_KEYS = ("grammage", "packageSize", "unit", "quantity", "subtitle",
             "weight", "description", "shortDescription", "basePrice")
BRAND_KEYS = ("brand", "brandName", "manufacturer")
BADGE_KEYS = ("discount", "discountText", "badge", "savings", "discountPercentage",
              "percentage", "advantage")

PRICE_RE = re.compile(r"(\d{1,4})[,.](\d{2})(?!\d)")
WHOLE_RE = re.compile(r"(?<![\d,.])(\d{1,4})[,.]\s?[-–]")
CENTS_RE = re.compile(r"(?<![\d])[-–]?[.,](\d{2})(?!\d)")
JUNK_TITLES = {"angebote", "angebot", "produkt", "prospekt", "mehr", "details"}


# ---------- разбор значений ----------

def parse_price(value, key=""):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if "cent" in key.lower():
            v /= 100
        return round(v, 2) if 0 < v < 5000 else None
    if isinstance(value, dict):
        for k in ("value", "amount", "price", "current", "raw", "formatted",
                  "priceValue", "valueInCents", "cents", "text"):
            if k in value:
                p = parse_price(value[k], k)
                if p:
                    return p
        return None
    if isinstance(value, str):
        s = value.replace("\xa0", " ")
        for rx, build in ((PRICE_RE, lambda m: f"{m.group(1)}.{m.group(2)}"),
                          (WHOLE_RE, lambda m: m.group(1)),
                          (CENTS_RE, lambda m: f"0.{m.group(1)}")):
            m = rx.search(s)
            if m:
                v = float(build(m))
                return v if 0 < v < 5000 else None
    return None


def text_of(value):
    if isinstance(value, str):
        s = re.sub(r"<[^>]+>", " ", value)
        s = re.sub(r"\s+", " ", s).strip()
        return s or None
    if isinstance(value, dict):
        for k in ("name", "text", "value", "label", "title"):
            if isinstance(value.get(k), str):
                return text_of(value[k])
    return None


def first_text(d, keys, max_len=160):
    for k in keys:
        if k in d:
            t = text_of(d[k])
            if t and 2 <= len(t) <= max_len:
                return t
    return None


def extract_image(value, depth=0):
    if value is None or depth > 3:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("//"):
            s = "https:" + s
        return s if s.startswith("http") else None
    if isinstance(value, list):
        for item in value:
            r = extract_image(item, depth + 1)
            if r:
                return r
    if isinstance(value, dict):
        for k in ("url", "src", "href", "original", "large", "medium", "default",
                  "imageUrl", "link"):
            if k in value:
                r = extract_image(value[k], depth + 1)
                if r:
                    return r
    return None


# ---------- поиск товаров в JSON ----------

def offer_from_dict(d):
    title = first_text(d, NAME_KEYS)
    if not title:
        return None
    price = None
    for k in PRICE_KEYS:
        if k in d:
            price = parse_price(d[k], k)
            if price:
                break
    if not price:
        return None
    old = None
    for k in OLD_KEYS:
        if k in d:
            old = parse_price(d[k], k)
            if old:
                break
    image = None
    for k in IMG_KEYS:
        if k in d:
            image = extract_image(d[k])
            if image:
                break
    return {
        "title": title,
        "brand": first_text(d, BRAND_KEYS, 60),
        "price": price,
        "old_price": old,
        "unit": first_text(d, UNIT_KEYS, 80),
        "image": image,
        "badge": first_text(d, BADGE_KEYS, 40),
    }


def find_offers(obj, found, depth=0):
    if depth > 40:
        return
    if isinstance(obj, dict):
        cand = offer_from_dict(obj)
        if cand:
            found.append(cand)
        for v in obj.values():
            find_offers(v, found, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            find_offers(v, found, depth + 1)


# ---------- приведение к общему виду ----------

def normalize(raw, store_id):
    title = re.sub(r"\s+", " ", raw["title"]).strip()
    if len(title) < 3 or title.lower() in JUNK_TITLES or not re.search(r"[A-Za-zÄÖÜäöüß]", title):
        return None
    brand = raw.get("brand")
    if brand and brand.isupper() and len(brand) > 3:
        brand = " ".join(w[:1].upper() + w[1:].lower() for w in brand.split())
    full = f"{brand} {title}" if brand and brand.lower() not in title.lower() else title
    price = raw["price"]
    old = raw.get("old_price")
    if old and old <= price:
        old = None
    discount = round((1 - price / old) * 100) if old else None
    if discount is None and raw.get("badge"):
        m = re.search(r"(\d{1,2})\s*%", raw["badge"])
        if m:
            discount = int(m.group(1))
    if discount is not None and not 1 <= discount <= 90:
        discount = None
    unit = raw.get("unit")
    if unit and (unit.lower() in full.lower() or len(unit) > 80):
        unit = None
    oid = hashlib.md5(f"{store_id}|{full.lower()}|{price}".encode()).hexdigest()[:12]
    return {
        "id": oid,
        "store": store_id,
        "title": full,
        "price": price,
        "old_price": old,
        "discount": discount,
        "unit": unit,
        "image": raw.get("image"),
        "link": raw.get("link"),
        "from": valid_from(raw.get("section")),
        "category": categorize(f"{full} {unit or ''}"),
    }


WEEKDAYS = {"mo": "пн", "di": "вт", "mi": "ср", "do": "чт", "fr": "пт", "sa": "сб"}


def valid_from(section):
    """'Ab-Do--29-10--Kindermode' -> 'с чт 29.10'"""
    m = re.match(r"ab-(mo|di|mi|do|fr|sa)\W*-+(\d{1,2})-(\d{1,2})", section or "", re.I)
    if not m:
        return None
    return f"с {WEEKDAYS[m.group(1).lower()]} {int(m.group(2)):02d}.{int(m.group(3)):02d}"


def merge(offers):
    """Убирает дубли; если один и тот же товар найден дважды, берёт лучшие поля."""
    by_id = {}
    for o in offers:
        if o is None:
            continue
        prev = by_id.get(o["id"])
        if prev is None:
            by_id[o["id"]] = o
        else:
            for k, v in o.items():
                if prev.get(k) in (None, "") and v not in (None, ""):
                    prev[k] = v
    return list(by_id.values())


# ---------- работа со страницей ----------

EMBEDDED_JS = """() => {
  const out = [];
  document.querySelectorAll('script[type="application/json"], script[type="application/ld+json"], script#__NEXT_DATA__')
    .forEach(s => { try { out.push(JSON.parse(s.textContent)); } catch (e) {} });
  for (const k of ['__NUXT__', '__INITIAL_STATE__', '__APOLLO_STATE__', '__PRELOADED_STATE__', '__STATE__']) {
    try { if (window[k]) out.push(JSON.parse(JSON.stringify(window[k]))); } catch (e) {}
  }
  return out;
}"""

DOM_JS = """() => {
  const out = [];
  const nodes = document.querySelectorAll(
    'article, li, [class*="product" i], [class*="offer" i], [class*="tile" i], [data-testid*="product" i]');
  for (const n of nodes) {
    const text = (n.innerText || '').trim();
    if (text.length < 5 || text.length > 500) continue;
    const h = n.querySelector('h2, h3, h4, [class*="title" i], [class*="name" i], [class*="headline" i]');
    const p = n.querySelector('[class*="price" i]:not([class*="old" i]):not([class*="strike" i]):not([class*="regular" i])');
    if (!h || !p) continue;
    const old = n.querySelector('s, del, [class*="old" i], [class*="strike" i], [class*="regular" i], [class*="uvp" i]');
    const badge = n.querySelector('[class*="discount" i], [class*="badge" i], [class*="percent" i]');
    const unit = n.querySelector('[class*="unit" i], [class*="grammage" i], [class*="quantity" i], [class*="amount" i]');
    const img = n.querySelector('img');
    out.push({
      title: h.innerText.trim(),
      price: p.innerText.trim(),
      old_price: old ? old.innerText.trim() : null,
      badge: badge ? badge.innerText.trim() : null,
      unit: unit ? unit.innerText.trim() : null,
      image: img ? (img.currentSrc || img.src || img.getAttribute('data-src')) : null,
    });
  }
  return out;
}"""


ALDI_JS = """() => [...document.querySelectorAll('.product-tile')].map(t => {
  const txt = (sel) => { const e = t.querySelector(sel); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; };
  const img = t.querySelector('img');
  const a = t.querySelector('a.product-tile__action, a[href*="/produkt/"]');
  const sec = t.closest('[data-hash]');
  return {
    brand: txt('[class*="brand-name"]'),
    title: txt('[class*="product-name"]'),
    price: txt('.tag__current') || txt('[class*="current-price"]'),
    old_price: txt('.tag__cross-price') || txt('.strike-price'),
    badge: txt('.tag__promo'),
    unit: txt('.tag__marker--salesunit'),
    image: img ? (img.currentSrc || img.src || null) : null,
    link: a ? a.href : null,
    section: sec ? sec.getAttribute('data-hash') : null,
  };
})"""

# Признаки страницы-заглушки, которую защита сайта показывает вместо акций
BLOCK_MARKERS = ("access denied", "waf block", "attention required",
                 "just a moment", "request unsuccessful", "you don't have permission",
                 "zugriff verweigert")


class Blocked(Exception):
    pass


async def check_blocked(page):
    try:
        head = ((await page.title()) + " " + (await page.inner_text("body"))[:3000]).lower()
    except Exception:
        return
    if any(m in head for m in BLOCK_MARKERS):
        raise Blocked("сайт магазина заблокировал доступ")


async def accept_cookies(page):
    for sel in ("#onetrust-accept-btn-handler", "[data-testid='uc-accept-all-button']",
                "#uc-btn-accept-banner", "button[data-accept-action='all']"):
        try:
            await page.click(sel, timeout=1500)
            return
        except Exception:
            pass
    try:
        rx = re.compile(r"(alle\s+)?(akzeptieren|zustimmen|erlauben)", re.I)
        await page.get_by_role("button", name=rx).first.click(timeout=2500)
    except Exception:
        pass


async def load_everything(page):
    more = re.compile(r"mehr anzeigen|weitere angebote|mehr laden|alle anzeigen", re.I)
    for _ in range(25):
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(700)
        try:
            btn = page.get_by_role("button", name=more).first
            if await btn.is_visible(timeout=300):
                await btn.click(timeout=1500)
                await page.wait_for_timeout(1200)
        except Exception:
            pass
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass


async def scrape_store(browser, store):
    ctx = await browser.new_context(locale="de-DE", timezone_id="Europe/Berlin",
                                    user_agent=UA, viewport={"width": 1366, "height": 900})
    await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = await ctx.new_page()
    payloads, tasks = [], []

    async def grab(resp):
        try:
            if "json" in resp.headers.get("content-type", ""):
                payloads.append((resp.url, await resp.json()))
        except Exception:
            pass

    page.on("response", lambda r: tasks.append(asyncio.ensure_future(grab(r))))
    debug = DEBUG_DIR / store["id"]
    debug.mkdir(parents=True, exist_ok=True)
    try:
        await page.goto(store["url"], wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)
        await check_blocked(page)
        await accept_cookies(page)
        await load_everything(page)
        await check_blocked(page)
        await asyncio.gather(*tasks, return_exceptions=True)

        raw, stats = [], []
        source = "json"
        if store.get("parser") == "aldi":
            source = "aldi"
            for item in await page.evaluate(ALDI_JS):
                price = parse_price(item.get("price"))
                if item.get("title") and price:
                    item["price"] = price
                    item["old_price"] = parse_price(item.get("old_price"))
                    raw.append(item)
        for url, data in payloads:
            found = []
            find_offers(data, found)
            stats.append({"url": url, "found": len(found)})
            raw.extend(found)
            if found and len([s for s in stats if s["found"]]) <= 20:
                (debug / f"api_{len(stats):02d}.json").write_text(
                    json.dumps(data, ensure_ascii=False)[:2_000_000], encoding="utf-8")
        for data in await page.evaluate(EMBEDDED_JS):
            find_offers(data, raw)
        if len(raw) < MIN_OFFERS:
            source = "dom"
            for item in await page.evaluate(DOM_JS):
                price = parse_price(item["price"])
                if price:
                    item["price"] = price
                    item["old_price"] = parse_price(item.get("old_price"))
                    raw.append(item)

        offers = merge(normalize(r, store["id"]) for r in raw)
        (debug / "summary.json").write_text(json.dumps(
            {"url": page.url, "source": source, "offers": len(offers), "responses": stats},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{store['name']}: {len(offers)} товаров (источник: {source})")
        return offers
    finally:
        try:
            (debug / "page.html").write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(debug / "screenshot.png"), full_page=False)
        except Exception:
            pass
        await ctx.close()


# ---------- запуск ----------

def load_previous():
    try:
        return json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        return {"stores": {}, "offers": []}


async def main():
    prev = load_previous()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    all_offers, status = [], {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
        for store in STORES:
            meta = {"name": store["name"], "color": store["color"], "url": store["url"]}
            if not store["url"].strip():
                print(f"{store['name']}: ссылка не указана, пропускаю")
                status[store["id"]] = {**meta, "ok": False, "error": "no_url",
                                       "updated": None, "count": 0}
                continue
            try:
                offers = await scrape_store(browser, store)
                if len(offers) < MIN_OFFERS:
                    raise RuntimeError(f"найдено только {len(offers)} товаров")
                status[store["id"]] = {**meta, "ok": True, "error": None,
                                       "updated": now, "count": len(offers)}
            except Exception as e:
                print(f"{store['name']}: ошибка: {e}", file=sys.stderr)
                if isinstance(e, Blocked):
                    e = "blocked"
                offers = [o for o in prev.get("offers", []) if o.get("store") == store["id"]]
                old = prev.get("stores", {}).get(store["id"], {})
                status[store["id"]] = {**meta, "ok": False, "error": str(e)[:200],
                                       "updated": old.get("updated"), "count": len(offers)}
            all_offers.extend(offers)
        await browser.close()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "updated": now,
        "stores": status,
        "categories": categories_for_site(),
        "offers": all_offers,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Сохранено {len(all_offers)} товаров в {OUTPUT}")

    if not any(s["ok"] for s in status.values()) and not all_offers:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
