#!/usr/bin/env python3
"""Scraper de leads de Meta Ads para Aether.

Busca en la Biblioteca de Anuncios de Meta negocios que ya están anunciando
(presupuesto confirmado) en los sectores del ICP, y saca un Excel priorizado
con web, contacto y por qué cada lead puntúa alto.

Modo recomendado: --mode api (necesita META_ACCESS_TOKEN, ver README.md).
Alternativa sin token: --mode browser (ejecútalo en TU ordenador, no en la
nube: Meta bloquea muchas IPs de servidores/hosting en la Ad Library web).

Ejemplos:
    python main.py --mode api --sectors joyeria cosmetica --max-ads 200
    python main.py --mode api --all-sectors --country ES
    python main.py --mode browser --sectors moda --no-headless
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

from leads.aggregate import aggregate
from leads.crm_export import export_for_crm
from leads.enrich import enrich_all
from leads.export import to_csv, to_xlsx
from leads.score import score_all
from leads.sectors import build_queries, load_sectors

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["api", "browser"], default="api",
                   help="api = Meta Ad Library API oficial (necesita token). "
                        "browser = Playwright, sin token, correr en local (por defecto: api)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--sectors", nargs="+", metavar="SECTOR",
                   help="Sectores a buscar (ver config/sectors.yaml). Por defecto: todos.")
    g.add_argument("--all-sectors", action="store_true", help="Busca todos los sectores del ICP.")
    p.add_argument("--keywords", nargs="+", default=[], help="Palabras clave sueltas adicionales.")
    p.add_argument("--country", default="ES", help="Código de país (por defecto ES).")
    p.add_argument("--max-ads", type=int, default=200, help="Máximo de anuncios por keyword (por defecto 200).")
    p.add_argument("--include-inactive", action="store_true",
                   help="Incluye anuncios ya finalizados, no solo activos (modo api).")
    p.add_argument("--no-enrich", action="store_true", help="No visitar la web de cada lead.")
    p.add_argument("--no-headless", action="store_true", help="(modo browser) muestra la ventana de Chromium.")
    p.add_argument("--out", default=None, help="Ruta del Excel de salida (por defecto output/leads_<fecha>.xlsx).")
    p.add_argument("--crm-json", default=None,
                   help="Además, escribe un JSON con el esquema exacto del CRM 'CRM {Meta Ads}' "
                        "(colección `leads`), listo para importar. Por defecto: output/crm_<fecha>.json")
    p.add_argument("--crm-tanda", type=int, default=1, help="Número de tanda a asignar en el CRM (por defecto 1).")
    p.add_argument("--crm-min-tier", choices=["A", "B", "C"], default="C",
                   help="Tier mínimo a incluir en el export del CRM (por defecto C = todos).")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )
    log = logging.getLogger("main")

    sectors_cfg = load_sectors()
    selected = None if args.all_sectors or not args.sectors else args.sectors
    queries = build_queries(sectors_cfg, selected, args.keywords)
    log.info("Buscando %d palabras clave en %d sector(es)…", len(queries), len({s for s, _ in queries}))

    ads = []
    if args.mode == "api":
        from leads.meta_api import MetaAdLibrary

        token = os.environ.get("META_ACCESS_TOKEN", "")
        client = MetaAdLibrary(token=token, country=args.country)
        for sector, kw in queries:
            log.info("[%s] %s", sector, kw)
            ads.extend(client.search(kw, sector, max_ads=args.max_ads,
                                      active_only=not args.include_inactive))
    else:
        from leads import browser

        log.info("Abriendo Chromium (modo browser)… esto puede tardar varios minutos.")
        ads = list(browser.search(queries, country=args.country, max_ads=args.max_ads,
                                   headless=not args.no_headless))

    log.info("Total de anuncios recogidos: %d", len(ads))
    leads = aggregate(ads)
    log.info("Anunciantes únicos: %d", len(leads))

    if not args.no_enrich:
        enrich_all(leads)

    score_all(leads)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = Path(args.out) if args.out else OUTPUT_DIR / f"leads_{datetime.now():%Y%m%d_%H%M}.xlsx"
    n = to_xlsx(leads, out_path)
    to_csv(leads, out_path.with_suffix(".csv"))
    log.info("Listo: %d leads exportados a %s", n, out_path)

    crm_path = Path(args.crm_json) if args.crm_json else OUTPUT_DIR / f"crm_{datetime.now():%Y%m%d_%H%M}.json"
    n_crm = export_for_crm(leads, crm_path, tanda=args.crm_tanda, min_tier=args.crm_min_tier)
    log.info("Export para el CRM: %d leads en %s (importa este JSON en la colección `leads`)", n_crm, crm_path)

    tiers = {"A": 0, "B": 0, "C": 0}
    for lead in leads.values():
        if not lead.excluded:
            tiers[lead.tier] = tiers.get(lead.tier, 0) + 1
    log.info("Tier A (prioridad alta): %d | Tier B: %d | Tier C: %d", tiers["A"], tiers["B"], tiers["C"])


if __name__ == "__main__":
    main()
