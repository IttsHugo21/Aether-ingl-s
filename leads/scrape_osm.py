#!/usr/bin/env python3
"""Extrae leads del ICP de Aether (marcas con producto físico) desde OpenStreetMap.

Uso: python3 leads/scrape_osm.py [--country ES] [--out leads/raw_osm.json]
Solo se guardan negocios con web propia (señal mínima de presupuesto/marketing).
"""
import argparse, json, sys, time, urllib.parse, urllib.request

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


def overpass(query):
    body = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(4):
        for url in ENDPOINTS:
            try:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": "aether-leads/1.0"})
                with urllib.request.urlopen(req, timeout=300) as r:
                    return json.load(r)["elements"]
            except Exception as e:  # endpoint caído o saturado: probar el siguiente
                last = e
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"Overpass falló: {last}")


def fetch_sector(country, shops):
    rx = "^(" + "|".join(shops) + ")$"
    q = f"""[out:json][timeout:280];
area["ISO3166-1"="{country}"][admin_level=2]->.a;
(nwr["shop"~"{rx}"]["website"](area.a);
 nwr["shop"~"{rx}"]["contact:website"](area.a););
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
    a = ap.parse_args()
    leads = []
    for sector, shops in SECTORS.items():
        els = fetch_sector(a.country, shops)
        print(f"{sector}: {len(els)}", file=sys.stderr, flush=True)
        leads += [to_lead(e, sector) for e in els]
        time.sleep(3)
    with open(a.out, "w") as f:
        json.dump(leads, f, ensure_ascii=False, indent=1)
    print(f"Total: {len(leads)} -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
