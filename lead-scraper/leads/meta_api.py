"""Cliente de la API oficial de la Biblioteca de Anuncios de Meta (ads_archive).

Desde la DSA (2023), para países de la UE la API devuelve TODOS los anuncios
(no solo políticos) con ad_type=ALL, incluido el alcance en la UE.
Docs: https://www.facebook.com/ads/library/api/
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from typing import Iterator

import requests

from .models import Ad

log = logging.getLogger(__name__)

API_VERSION = "v23.0"
FIELDS = ",".join(
    [
        "id",
        "page_id",
        "page_name",
        "ad_delivery_start_time",
        "ad_delivery_stop_time",
        "ad_creative_bodies",
        "ad_creative_link_captions",
        "ad_creative_link_titles",
        "ad_creative_link_descriptions",
        "ad_snapshot_url",
        "publisher_platforms",
        "eu_total_reach",
        "beneficiary_payers",
    ]
)
# Códigos de límite de uso: esperar y reintentar.
RATE_LIMIT_CODES = {4, 17, 32, 613, 80004}


class MetaApiError(RuntimeError):
    pass


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")[:10]).date()
    except ValueError:
        return None


def _payer(raw: dict) -> str:
    items = raw.get("beneficiary_payers") or []
    if isinstance(items, dict):
        items = items.get("data", [])
    parts = []
    for it in items:
        if isinstance(it, dict):
            parts.extend(v for v in (it.get("payer"), it.get("beneficiary")) if v)
    return " / ".join(dict.fromkeys(parts))


def normalize(raw: dict, keyword: str, sector: str) -> Ad:
    reach = raw.get("eu_total_reach")
    return Ad(
        ad_id=str(raw["id"]),
        page_id=str(raw.get("page_id", "")),
        page_name=raw.get("page_name", "") or "",
        keyword=keyword,
        sector=sector,
        source="api",
        start_date=_parse_date(raw.get("ad_delivery_start_time")),
        stop_date=_parse_date(raw.get("ad_delivery_stop_time")),
        bodies=[b for b in raw.get("ad_creative_bodies") or [] if b],
        link_captions=[c for c in raw.get("ad_creative_link_captions") or [] if c]
        + [t for t in raw.get("ad_creative_link_titles") or [] if t and "." in t],
        platforms=raw.get("publisher_platforms") or [],
        eu_reach=int(reach) if isinstance(reach, (int, float, str)) and str(reach).isdigit() else None,
        payer=_payer(raw),
        snapshot_url=raw.get("ad_snapshot_url", "") or "",
    )


class MetaAdLibrary:
    def __init__(self, token: str, country: str = "ES", version: str = API_VERSION,
                 session: requests.Session | None = None, pause: float = 1.0):
        if not token:
            raise MetaApiError(
                "Falta META_ACCESS_TOKEN. Mira el README para obtener el token."
            )
        self.token = token
        self.country = country
        self.url = f"https://graph.facebook.com/{version}/ads_archive"
        self.session = session or requests.Session()
        self.pause = pause

    def _get(self, url: str, params: dict | None) -> dict:
        for attempt in range(6):
            resp = self.session.get(url, params=params, timeout=60)
            try:
                data = resp.json()
            except ValueError:
                data = {"error": {"message": resp.text[:300], "code": resp.status_code}}
            err = data.get("error")
            if not err:
                return data
            code = err.get("code")
            if code in RATE_LIMIT_CODES or resp.status_code >= 500:
                wait = min(60 * (attempt + 1), 300)
                log.warning("Límite de la API (%s). Espero %ss…", code, wait)
                time.sleep(wait)
                continue
            if code == 190:
                raise MetaApiError("Token caducado o inválido (código 190). Genera uno nuevo.")
            if code == 10 or err.get("error_subcode") == 2332002:
                raise MetaApiError(
                    "Tu app no tiene acceso a la Ad Library API. Confirma tu identidad en "
                    "facebook.com/ID y acepta las condiciones en facebook.com/ads/library/api."
                )
            raise MetaApiError(f"Error de la API de Meta: {err.get('message')} (código {code})")
        raise MetaApiError("Demasiados reintentos por límite de uso.")

    def search(self, keyword: str, sector: str, max_ads: int = 500,
               active_only: bool = True, min_start: date | None = None) -> Iterator[Ad]:
        params = {
            "access_token": self.token,
            "search_terms": keyword,
            "search_type": "KEYWORD_UNORDERED",
            "ad_type": "ALL",
            "ad_reached_countries": json.dumps([self.country]),
            "ad_active_status": "ACTIVE" if active_only else "ALL",
            "fields": FIELDS,
            "limit": 200,
        }
        if min_start:
            params["ad_delivery_date_min"] = min_start.isoformat()
        url, count = self.url, 0
        while url and count < max_ads:
            data = self._get(url, params)
            for raw in data.get("data", []):
                if count >= max_ads:
                    break
                count += 1
                yield normalize(raw, keyword, sector)
            url = (data.get("paging") or {}).get("next")
            params = None  # "next" ya incluye todos los parámetros
            time.sleep(self.pause)
        log.info("  %s: %d anuncios", keyword, count)
