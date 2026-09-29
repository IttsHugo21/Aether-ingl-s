"""Puntuación de leads: prioriza negocios que YA invierten en Meta Ads
(presupuesto confirmado) y que parecen poder pagar anuncios hiperrealistas
con IA (marca propia, no un simple revendedor/marketplace).
"""
from __future__ import annotations

from datetime import date

from .models import Lead
from .sectors import load_blocklist


def _matches_blocklist(lead: Lead, blocklist: list[str]) -> str:
    name = lead.page_name.lower()
    haystacks = [name, *(d.lower() for d in lead.domains)]
    for term in blocklist:
        if any(term in h for h in haystacks):
            return term
    return ""


def score_lead(lead: Lead, blocklist: list[str], today: date | None = None) -> None:
    hit = _matches_blocklist(lead, blocklist)
    if hit:
        lead.excluded = f'coincide con blocklist ("{hit}")'
        lead.score = 0
        lead.tier = "excluido"
        return

    score = 0
    reasons: list[str] = []

    n_ads = lead.active_ads
    if n_ads >= 10:
        score += 30
        reasons.append(f"{n_ads} anuncios activos (inversión alta)")
    elif n_ads >= 4:
        score += 20
        reasons.append(f"{n_ads} anuncios activos")
    elif n_ads >= 1:
        score += 10
        reasons.append(f"{n_ads} anuncio(s) activo(s)")

    days = lead.days_running(today)
    if days >= 60:
        score += 20
        reasons.append(f"campaña activa desde hace {days} días (gasto sostenido)")
    elif days >= 21:
        score += 12
        reasons.append(f"campaña activa desde hace {days} días")
    elif days >= 7:
        score += 6

    creatives = lead.distinct_creatives
    if creatives >= 5:
        score += 15
        reasons.append(f"{creatives} creatividades distintas (testean mucho => presupuesto)")
    elif creatives >= 2:
        score += 8

    reach = lead.eu_reach
    if reach:
        if reach >= 100_000:
            score += 15
            reasons.append(f"alcance UE estimado {reach:,}")
        elif reach >= 20_000:
            score += 8

    if lead.website:
        score += 10
        reasons.append("web propia detectada")
    if lead.platform in ("Shopify", "WooCommerce/WordPress", "PrestaShop"):
        score += 5
        reasons.append(f"e-commerce propio ({lead.platform})")
    if lead.has_meta_pixel:
        score += 5
        reasons.append("pixel de Meta instalado (rastrea conversiones => sabe de performance)")
    if lead.emails or lead.phones or lead.whatsapp:
        score += 5
        reasons.append("contacto directo encontrado (email/tel/WhatsApp)")

    if "instagram" in lead.platforms:
        score += 3
    if len(lead.platforms) >= 2:
        score += 2

    lead.score = min(score, 100)
    lead.reasons = reasons
    if lead.score >= 65:
        lead.tier = "A"
    elif lead.score >= 40:
        lead.tier = "B"
    else:
        lead.tier = "C"


def score_all(leads: dict[str, Lead], blocklist_path=None) -> None:
    blocklist = load_blocklist(blocklist_path)
    for lead in leads.values():
        score_lead(lead, blocklist)
