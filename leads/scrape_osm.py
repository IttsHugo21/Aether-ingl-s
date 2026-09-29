#!/usr/bin/env python3
"""Extrae leads del ICP de Aether (marcas con producto físico) desde OpenStreetMap.

Uso: python3 leads/scrape_osm.py [--country ES] [--out leads/raw_osm.json]
Solo se guardan negocios con web propia (señal mínima de presupuesto/marketing).

Resiliente: guarda el resultado de cada sector en leads/cache/<sector>.json
según se va obteniendo, así que un timeout o corte a media ejecución no
pierde el trabajo ya hecho. Al relanzar, los sectores ya cacheados se
saltan (usa --force para repetirlos todos).
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request

ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Sector del ICP -> valores de la etiqueta shop=* en OSM
SECTORS = {
    "Joyería": ["jewelry"],
    "Cosmética / belleza": ["cosmetics", "perfumery", "hairdresser_supply"],
    "Moda": ["clothes", "boutique", "fashion"],
    "Calzado": ["shoes"],
    "Accesorios": ["bag", "leather", "fashion_accessories", "optician", "watches"],
    "Hogar / decoración": ["furniture", "interior_decoration", "lighting", "candles", "houseware", "bed"],
    "Deporte": ["sports", "outdoor", "bicycle", "nutrition_supplements", "fishing", "golf"],
    "Mascotas": ["pet"],
    "Alimentación premium": ["coffee", "chocolate", "confectionery", "tea", "deli", "wine", "cheese", "pastry"],
    "Electrónica": ["electronics", "mobile_phone", "hifi", "computer"],
}

CACHE_DIR = "leads/cache"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def overpass(query, attempts=5):
    body = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(attempts):
        for url in ENDPOINTS:
            try:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": "aether-leads/1.0"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.load(r)["elements"]
            except Exception as e:  # endpoint caído, saturado o timeout: probar el siguiente
                last = e
                print(f"    endpoint fallo ({url}): {e}", file=sys.stderr, flush=True)
        time.sleep(min(2 ** (attempt + 1), 30))
    raise RuntimeError(f"Overpass falló tras {attempts} intentos: {last}")


def fetch_sector(country, shops, timeout_s=120):
    rx = "^(" + "|".join(shops) + ")$"
    q = f"""[out:json][timeout:{timeout_s}];
area["ISO3166-1"="{country}"][admin_level=2]->.a;
(nwr["shop"~"{rx}"]["website"](area.a);
 nwr["shop"~"{rx}"]["contact:website"](area.a));
out center tags;"""
    return overpass(q)


def to_lead(el, sector):
    t = el.get("tags", {})
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lon = el.get("lon") or el.get("center", {}).get("lon")
    return {
        "osm_id": f"{el['type']}/{el['id']}",
        "name": t.get("name") or t.get("brand") or "",
        "sector": sector,
        "shop": t.get("shop"),
        "website": t.get("website") or t.get("contact:website"),
        "phone": t.get("phone") or t.get("contact:phone") or t.get("contact:mobile") or "",
        "email": t.get("email") or t.get("contact:email") or "",
        "instagram": t.get("contact:instagram") or "",
        "facebook": t.get("contact:facebook") or "",
        "city": t.get("addr:city") or "",
        "postcode": t.get("addr:postcode") or "",
        "street": " ".join(x for x in [t.get("addr:street"), t.get("addr:housenumber")] if x),
        "brand": t.get("brand") or "",
        "is_chain": bool(t.get("brand:wikidata")),
        "lat": lat, "lon": lon,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="ES")
    ap.add_argument("--out", default="leads/raw_osm.json")
    ap.add_argument("--force", action="store_true", help="reintenta también los sectores ya cacheados")
    a = ap.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)
    failed = []

    for sector, shops in SECTORS.items():
        cache_path = os.path.join(CACHE_DIR, slug(sector) + ".json")
        if os.path.exists(cache_path) and not a.force:
            with open(cache_path) as f:
                n = len(json.load(f))
            print(f"{sector}: {n} (cache)", file=sys.stderr, flush=True)
            continue
        try:
            els = fetch_sector(a.country, shops)
        except Exception as e:
            print(f"{sector}: FALLÓ ({e}) — se reintentará en la próxima ejecución", file=sys.stderr, flush=True)
            failed.append(sector)
            continue
        leads = [to_lead(e, sector) for e in els]
        with open(cache_path, "w") as f:
            json.dump(leads, f, ensure_ascii=False, indent=1)
        print(f"{sector}: {len(els)}", file=sys.stderr, flush=True)
        time.sleep(3)

    # Combina todo lo que haya en cache (de esta ejecución y de anteriores)
    all_leads = []
    for sector in SECTORS:
        cache_path = os.path.join(CACHE_DIR, slug(sector) + ".json")
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                all_leads += json.load(f)

    with open(a.out, "w") as f:
        json.dump(all_leads, f, ensure_ascii=False, indent=1)
    print(f"Total: {len(all_leads)} -> {a.out}", file=sys.stderr)

    if failed:
        print(f"Sectores pendientes (relanza el script para reintentarlos): {', '.join(failed)}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
