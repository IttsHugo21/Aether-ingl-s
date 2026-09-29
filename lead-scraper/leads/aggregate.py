from __future__ import annotations

import re
from collections import Counter
from typing import Iterable
from urllib.parse import urlparse

from .models import Ad, Lead

# Dominios que no son la web del anunciante.
NON_WEBSITE = (
    "facebook.com", "fb.me", "fb.com", "instagram.com", "messenger.com", "wa.me",
    "whatsapp.com", "api.whatsapp.com", "linktr.ee", "bit.ly", "tiktok.com",
    "youtube.com", "youtu.be", "google.com", "goo.gl", "forms.gle", "apps.apple.com",
    "play.google.com", "amazon.es", "amazon.com", "t.co", "l.facebook.com",
)
DOMAIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+(?:es|com|net|org|eu|shop|store|cat|co|io|online|me|pt|fr|it|de|boutique|beauty|fashion|style))\b",
    re.I,
)


def _domain_from(text: str) -> str | None:
    text = text.strip()
    if text.startswith("http"):
        host = urlparse(text).netloc.lower()
        host = host.removeprefix("www.")
        return host or None
    m = DOMAIN_RE.search(text)
    return m.group(1).lower() if m else None


def _is_website(domain: str) -> bool:
    return not any(domain == d or domain.endswith("." + d) for d in NON_WEBSITE)


def aggregate(ads: Iterable[Ad]) -> dict[str, Lead]:
    leads: dict[str, Lead] = {}
    for ad in ads:
        if not ad.page_id:
            continue
        lead = leads.get(ad.page_id)
        if not lead:
            lead = leads[ad.page_id] = Lead(page_id=ad.page_id, page_name=ad.page_name)
        lead.page_name = lead.page_name or ad.page_name
        lead.sectors.add(ad.sector)
        lead.keywords.add(ad.keyword)
        lead.ads.setdefault(ad.ad_id, ad)
        lead.payer = lead.payer or ad.payer
        lead.page_profile_url = lead.page_profile_url or ad.page_profile_url
        if ad.page_likes:
            lead.page_likes = ad.page_likes

    for lead in leads.values():
        counts: Counter[str] = Counter()
        for ad in lead.ads.values():
            for src in [*ad.link_urls, *ad.link_captions]:
                d = _domain_from(src)
                if d:
                    counts[d] += 2  # más fiable que el texto del anuncio
            for body in ad.bodies:
                for m in DOMAIN_RE.finditer(body):
                    counts[m.group(1).lower()] += 1
        lead.domains = [d for d, _ in counts.most_common()]
        own = [d for d in lead.domains if _is_website(d)]
        lead.website = f"https://{own[0]}" if own else ""
        for d in lead.domains:
            if "instagram.com" in d:
                lead.instagram = lead.instagram or d
    return leads
