from datetime import date, timedelta

from leads.models import Ad, Lead
from leads.score import score_all, score_lead


def lead_with(n_ads=1, days_ago=0, website="", platform="", meta_pixel=False,
              page_name="Marca X", domains=None):
    lead = Lead(page_id="p1", page_name=page_name)
    start = date.today() - timedelta(days=days_ago)
    for i in range(n_ads):
        lead.ads[str(i)] = Ad(
            ad_id=str(i), page_id="p1", page_name=page_name, keyword="k",
            sector="s", source="api", start_date=start, bodies=[f"anuncio {i}"],
        )
    lead.website = website
    lead.platform = platform
    lead.has_meta_pixel = meta_pixel
    lead.domains = domains or []
    return lead


def test_high_activity_scores_tier_a():
    lead = lead_with(n_ads=12, days_ago=90, website="https://x.com", platform="Shopify", meta_pixel=True)
    score_lead(lead, blocklist=[])
    assert lead.tier == "A"
    assert lead.score >= 65
    assert lead.reasons


def test_low_activity_scores_tier_c():
    lead = lead_with(n_ads=1, days_ago=1)
    score_lead(lead, blocklist=[])
    assert lead.tier == "C"


def test_blocklisted_page_name_is_excluded():
    lead = lead_with(n_ads=20, days_ago=200, page_name="Amazon España")
    score_lead(lead, blocklist=["amazon"])
    assert lead.excluded
    assert lead.score == 0
    assert lead.tier == "excluido"


def test_blocklisted_domain_is_excluded():
    lead = lead_with(n_ads=5, days_ago=30, domains=["zara.com"])
    score_lead(lead, blocklist=["zara"])
    assert lead.excluded


def test_score_all_runs_without_config_path_override(tmp_path):
    blocklist_file = tmp_path / "blocklist.txt"
    blocklist_file.write_text("amazon\n", encoding="utf-8")
    leads = {"p1": lead_with(n_ads=3, days_ago=10)}
    score_all(leads, blocklist_path=blocklist_file)
    assert leads["p1"].tier in {"A", "B", "C"}
