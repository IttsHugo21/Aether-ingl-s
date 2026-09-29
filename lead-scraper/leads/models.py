from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Ad:
    """Un anuncio normalizado, venga de la API o del navegador."""

    ad_id: str
    page_id: str
    page_name: str
    keyword: str
    sector: str
    source: str  # "api" | "browser"
    start_date: date | None = None
    stop_date: date | None = None
    bodies: list[str] = field(default_factory=list)
    link_captions: list[str] = field(default_factory=list)  # dominios / captions
    link_urls: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    eu_reach: int | None = None
    payer: str = ""
    snapshot_url: str = ""
    page_likes: int | None = None
    page_profile_url: str = ""


@dataclass
class Lead:
    """Un anunciante (página de Facebook) con todos sus anuncios agregados."""

    page_id: str
    page_name: str
    sectors: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)
    ads: dict[str, Ad] = field(default_factory=dict)
    website: str = ""
    domains: list[str] = field(default_factory=list)
    page_profile_url: str = ""
    page_likes: int | None = None
    payer: str = ""

    # Enriquecimiento web
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    whatsapp: str = ""
    instagram: str = ""
    tiktok: str = ""
    platform: str = ""  # shopify, woocommerce...
    has_meta_pixel: bool = False
    has_tiktok_pixel: bool = False
    web_status: str = ""

    # Scoring
    score: int = 0
    tier: str = ""
    reasons: list[str] = field(default_factory=list)
    excluded: str = ""

    @property
    def active_ads(self) -> int:
        return len(self.ads)

    @property
    def distinct_creatives(self) -> int:
        texts = {" ".join(a.bodies).strip().lower() for a in self.ads.values()}
        texts.discard("")
        return max(len(texts), 1 if self.ads else 0)

    @property
    def first_seen(self) -> date | None:
        dates = [a.start_date for a in self.ads.values() if a.start_date]
        return min(dates) if dates else None

    def days_running(self, today: date | None = None) -> int:
        first = self.first_seen
        if not first:
            return 0
        return ((today or date.today()) - first).days

    @property
    def eu_reach(self) -> int | None:
        reaches = [a.eu_reach for a in self.ads.values() if a.eu_reach is not None]
        return sum(reaches) if reaches else None

    @property
    def platforms(self) -> list[str]:
        out: set[str] = set()
        for a in self.ads.values():
            out.update(p.lower() for p in a.platforms)
        return sorted(out)

    @property
    def ad_library_url(self) -> str:
        return (
            "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
            f"&country=ES&view_all_page_id={self.page_id}"
        )

    @property
    def sample_ad(self) -> str:
        for a in sorted(self.ads.values(), key=lambda a: a.start_date or date.max):
            if a.bodies and a.bodies[0].strip():
                return a.bodies[0].strip()[:300]
        return ""
