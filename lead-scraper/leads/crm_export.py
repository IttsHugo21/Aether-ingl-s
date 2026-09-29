"""Convierte los leads puntuados al esquema exacto que espera el CRM
"CRM {Meta Ads}" (artifact de claude.ai), para importarlos en su
colección `leads`.

Campos del CRM (uno por documento, doc_id = marca en slug):
    marca, sector, pais, web, anuncio_url, num_anuncios, tanda,
    estado, notas, fecha_tanda

Este módulo NO escribe en el artifact directamente (esa base de datos
vive en otra organización de claude.ai y esta sesión no tiene acceso
a ella) — solo genera el JSON con la forma correcta para que:
  a) lo importes desde una sesión que sí sea dueña del artifact, o
  b) los añadas a mano con el botón "+ Añadir lead" del propio CRM.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from .models import Lead


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "lead"


def _unique_id(base: str, used: set[str]) -> str:
    doc_id, n = base, 1
    while doc_id in used:
        n += 1
        doc_id = f"{base}-{n}"
    used.add(doc_id)
    return doc_id


def lead_to_crm_doc(lead: Lead, tanda: int, country_label: str = "España") -> dict:
    return {
        "marca": lead.page_name or "(sin nombre)",
        "sector": ", ".join(sorted(lead.sectors)) or None,
        "pais": country_label,
        "web": lead.website or None,
        "anuncio_url": lead.ad_library_url,
        "num_anuncios": lead.active_ads or None,
        "tanda": tanda,
        "estado": "pendiente",
        "notas": " · ".join(lead.reasons[:3]) if lead.reasons else "",
        "fecha_tanda": date.today().isoformat(),
    }


def export_for_crm(
    leads: dict[str, Lead], path: Path, tanda: int = 1,
    min_tier: str = "C", country_label: str = "España",
) -> int:
    """Escribe un JSON {doc_id: documento} listo para importar al CRM.

    Solo incluye leads no excluidos y con tier igual o mejor que min_tier
    (A > B > C). Por defecto incluye A, B y C.
    """
    order = {"A": 0, "B": 1, "C": 2}
    threshold = order.get(min_tier, 2)
    docs: dict[str, dict] = {}
    used: set[str] = set()
    ranked = sorted(
        (l for l in leads.values() if not l.excluded and order.get(l.tier, 9) <= threshold),
        key=lambda l: l.score, reverse=True,
    )
    for lead in ranked:
        doc_id = _unique_id(_slugify(lead.page_name), used)
        docs[doc_id] = lead_to_crm_doc(lead, tanda=tanda, country_label=country_label)

    path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(docs)
