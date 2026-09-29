#!/usr/bin/env python3
"""Enriquece y puntúa los leads de raw_osm.json visitando su web.

Detecta: tienda online (Shopify/WooCommerce/PrestaShop/Magento...), píxel de
Meta y etiqueta de Google Ads (= ya invierten en publicidad), email e Instagram.
Uso: python3 leads/enrich.py [--in leads/raw_osm.json] [--out leads/leads.json]
"""
import argparse, concurrent.futures as cf, json, re, sys, urllib.parse, urllib.request
from collections import defaultdict

SOCIAL = ("facebook.com", "instagram.com", "linktr.ee", "google.com", "wa.me", "tiktok.com",
          "business.site", "wixsite.com", "blogspot.com", "tripadvisor", "paginasamarillas")
PRIORITY = {"Joyería", "Cosmética / belleza", "Moda", "Calzado", "Accesorios"}
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,6}")
IG_RX = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})")
BAD_IG = {"p", "explore", "accounts", "reel", "reels", "stories", "share", "instagram", "tv"}
BAD_EMAIL = ("example", "sentry", "wixpress", "domain.", "email.", "@2x", ".png", ".jpg", ".webp", "yourname", "u003e")
PLATFORMS = [("Shopify", "cdn.shopify.com"), ("WooCommerce", "woocommerce"), ("PrestaShop", "prestashop"),
             ("Magento", "mage/"), ("Wix Stores", "wixstores"), ("Squarespace", "squarespace-commerce"),
             ("VTEX", "vtex"), ("Tiendanube", "tiendanube"), ("Shopify", "myshopify.com")]
CART_HINTS = ("añadir al carrito", "add to cart", "anadir al carrito", "/cart", "/carrito", "comprar ahora", "/checkout")


def domain(url):
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    h = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def fetch(url):
    if "://" not in url:
        url = "https://" + url
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return r.read(600_000).decode("utf-8", "ignore"), r.geturl()


def inspect(url):
    try:
        html, final = fetch(url)
    except Exception as e:
        return {"web_ok": False, "web_error": type(e).__name__}
    low = html.lower()
    platform = next((n for n, sig in PLATFORMS if sig in low), "")
    emails = [m for m in EMAIL_RX.findall(html) if not any(b in m.lower() for b in BAD_EMAIL)]
    igs = [h for h in IG_RX.findall(html) if h.lower() not in BAD_IG]
    return {
        "web_ok": True,
        "final_url": final,
        "platform": platform,
        "ecommerce": bool(platform) or any(h in low for h in CART_HINTS),
        "meta_pixel": "fbq(" in low or "connect.facebook.net" in low,
        "google_ads": bool(re.search(r"aw-\d{6,}", low)) or "googleadservices" in low,
        "tiktok_pixel": "analytics.tiktok.com" in low,
        "email_web": emails[0].lower() if emails else "",
        "instagram_web": igs[0] if igs else "",
    }


def score(l):
    s = 0
    s += 30 if l.get("ecommerce") else 0
    s += 5 if l.get("platform") == "Shopify" else 0
    s += 15 if l.get("meta_pixel") else 0
    s += 10 if l.get("google_ads") else 0
    s += 5 if l.get("tiktok_pixel") else 0
    s += 10 if l.get("instagram") else 0
    s += 10 if l.get("email") else 0
    s += 5 if l.get("phone") else 0
    s += 5 if 2 <= l.get("locations", 1) <= 25 else 0
    s += 5 if l["sector"] in PRIORITY else 0
    return min(s, 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="leads/raw_osm.json")
    ap.add_argument("--out", default="leads/leads.json")
    ap.add_argument("--workers", type=int, default=40)
    a = ap.parse_args()
    raw = json.load(open(a.inp))

    # Una fila por dominio (varias tiendas de la misma marca comparten web).
    groups = defaultdict(list)
    for l in raw:
        d = domain(l["website"])
        if d and not any(s in d for s in SOCIAL) and not l["is_chain"]:
            groups[d].append(l)
    leads = []
    for d, ls in groups.items():
        base = dict(max(ls, key=lambda x: sum(bool(v) for v in x.values())))
        base["domain"] = d
        base["locations"] = len(ls)
        base["cities"] = sorted({x["city"] for x in ls if x["city"]})[:8]
        leads.append(base)
    print(f"{len(raw)} en bruto -> {len(leads)} marcas únicas (sin cadenas ni webs sociales)", file=sys.stderr)

    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(inspect, l["website"]): l for l in leads}
        for i, f in enumerate(cf.as_completed(futs), 1):
            l = futs[f]
            l.update(f.result())
            l["email"] = l["email"] or l.pop("email_web", "")
            ig = l["instagram"] or l.pop("instagram_web", "")
            l["instagram"] = ig.rstrip("/").split("/")[-1].lstrip("@") if ig else ""
            l["score"] = score(l)
            if i % 250 == 0:
                print(f"  {i}/{len(leads)}", file=sys.stderr, flush=True)

    leads = [l for l in leads if l.get("web_ok")]
    leads.sort(key=lambda l: -l["score"])
    json.dump(leads, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"{len(leads)} con web operativa -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
