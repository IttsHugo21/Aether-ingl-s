"""Alternativa sin token: abre la Biblioteca de Anuncios en Chromium (Playwright)
y lee las respuestas JSON que la propia web recibe mientras haces scroll.

Úsalo en TU ordenador (Meta bloquea muchas IPs de servidores/cloud).
Instalación: pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterator
from urllib.parse import quote

from .models import Ad

log = logging.getLogger(__name__)

LIBRARY_URL = (
    "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
    "&country={country}&q={q}&search_type=keyword_unordered&media_type=all"
)


def _walk(node: Any) -> Iterator[dict]:
    """Recorre cualquier JSON y devuelve los objetos que parecen anuncios."""
    if isinstance(node, dict):
        if "ad_archive_id" in node and "snapshot" in node:
            yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _json_chunks(text: str) -> Iterator[Any]:
    text = text.removeprefix("for (;;);")
    for line in text.splitlines() or [text]:
        line = line.strip()
        if line.startswith(("{", "[")):
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _ts(value: Any):
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date()
    except (TypeError, ValueError, OSError):
        return None


def normalize(raw: dict, keyword: str, sector: str) -> Ad | None:
    snap = raw.get("snapshot") or {}
    page_id = str(raw.get("page_id") or snap.get("page_id") or "")
    if not page_id:
        return None
    bodies, urls, captions = [], [], []
    body = snap.get("body")
    if isinstance(body, dict):
        body = body.get("text")
    if body:
        bodies.append(body)
    for src in [snap, *(snap.get("cards") or [])]:
        if src.get("link_url"):
            urls.append(src["link_url"])
        if src.get("caption"):
            captions.append(src["caption"])
        if src is not snap and src.get("body"):
            bodies.append(src["body"])
    platforms = raw.get("publisher_platform") or raw.get("publisher_platforms") or []
    return Ad(
        ad_id=str(raw["ad_archive_id"]),
        page_id=page_id,
        page_name=raw.get("page_name") or snap.get("page_name") or "",
        keyword=keyword,
        sector=sector,
        source="browser",
        start_date=_ts(raw.get("start_date")),
        stop_date=_ts(raw.get("end_date")),
        bodies=bodies,
        link_captions=captions,
        link_urls=urls,
        platforms=[p for p in platforms if isinstance(p, str)],
        page_likes=snap.get("page_like_count"),
        page_profile_url=snap.get("page_profile_uri") or "",
    )


def search(keywords: list[tuple[str, str]], country: str = "ES", max_ads: int = 300,
           headless: bool = False, max_scrolls: int = 40) -> Iterator[Ad]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit(
            "Falta Playwright: pip install playwright && python -m playwright install chromium"
        ) from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(locale="es-ES", viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        for sector, kw in keywords:
            found: dict[str, dict] = {}

            def on_response(resp):
                if "/api/graphql" not in resp.url:
                    return
                try:
                    for chunk in _json_chunks(resp.text()):
                        for raw in _walk(chunk):
                            found.setdefault(str(raw["ad_archive_id"]), raw)
                except Exception:  # respuestas binarias o cortadas
                    pass

            page.on("response", on_response)
            page.goto(LIBRARY_URL.format(country=country, q=quote(kw)), wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            # Primeros resultados: vienen incrustados en el HTML.
            for blob in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', page.content(), re.S):
                for chunk in _json_chunks(blob):
                    for raw in _walk(chunk):
                        found.setdefault(str(raw["ad_archive_id"]), raw)
            stale = 0
            for _ in range(max_scrolls):
                if len(found) >= max_ads:
                    break
                before = len(found)
                page.mouse.wheel(0, 6000)
                page.wait_for_timeout(1800)
                stale = stale + 1 if len(found) == before else 0
                if stale >= 4:
                    break
            page.remove_listener("response", on_response)
            log.info("  %s: %d anuncios", kw, len(found))
            for raw in list(found.values())[:max_ads]:
                ad = normalize(raw, kw, sector)
                if ad:
                    yield ad
        browser.close()
