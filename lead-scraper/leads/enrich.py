"""Enriquecimiento: visita la web del lead (si la tenemos) y extrae señales
de contacto y de stack técnico. Va después del scraping de Meta, es opcional
(--no-enrich lo desactiva) y tolera fallos por lead sin tumbar el proceso.
"""
from __future__ import annotations

import logging
import re
import time

import requests

from .models import Lead

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+34[\s.-]?)?(?:6|7|9)\d{2}[\s.-]?\d{2,3}[\s.-]?\d{2,3}[\s.-]?\d{0,3}")
WHATSAPP_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d{9,15})")
IG_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})")
TT_RE = re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{2,30})")
BAD_EMAIL_DOMAINS = ("sentry.io", "wixpress.com", "example.com", "w3.org", "schema.org")


def _clean_emails(text: str) -> list[str]:
    found = {m.group(0).lower() for m in EMAIL_RE.finditer(text)}
    return sorted(e for e in found if not any(d in e for d in BAD_EMAIL_DOMAINS))[:5]


def enrich_lead(lead: Lead, session: requests.Session, timeout: float = 12.0, pause: float = 0.5) -> None:
    if not lead.website:
        lead.web_status = "sin web detectada"
        return
    try:
        resp = session.get(
            lead.website, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True
        )
        html = resp.text
        lead.web_status = f"HTTP {resp.status_code}"
    except requests.RequestException as e:
        lead.web_status = f"error: {type(e).__name__}"
        return
    finally:
        time.sleep(pause)

    lead.emails = _clean_emails(html)
    phones = {re.sub(r"[\s.-]", "", m.group(0)) for m in PHONE_RE.finditer(html)}
    lead.phones = sorted(p for p in phones if len(p) >= 9)[:5]
    wa = WHATSAPP_RE.search(html)
    if wa:
        lead.whatsapp = wa.group(1)
    ig = IG_RE.search(html)
    if ig and ig.group(1) not in ("p", "reel", "explore"):
        lead.instagram = lead.instagram or ig.group(1)
    tt = TT_RE.search(html)
    if tt:
        lead.tiktok = tt.group(1)

    lower = html.lower()
    if "cdn.shopify.com" in lower or "shopify" in lower:
        lead.platform = "Shopify"
    elif "woocommerce" in lower or "wp-content" in lower:
        lead.platform = "WooCommerce/WordPress"
    elif "prestashop" in lower:
        lead.platform = "PrestaShop"
    elif "cdn.builder" in lower or "wix.com" in lower:
        lead.platform = "Wix"

    lead.has_meta_pixel = "connect.facebook.net" in lower and "fbevents.js" in lower
    lead.has_tiktok_pixel = "analytics.tiktok.com" in lower or "ttq.load" in lower


def enrich_all(leads: dict[str, Lead], workers: int = 8) -> None:
    from concurrent.futures import ThreadPoolExecutor

    session = requests.Session()
    todo = [l for l in leads.values() if l.website]
    log.info("Enriqueciendo %d webs (de %d leads totales)…", len(todo), len(leads))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda l: enrich_lead(l, session), todo))
