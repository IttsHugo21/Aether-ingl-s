from leads.aggregate import aggregate
from leads.models import Ad


def make_ad(**kwargs):
    defaults = dict(
        ad_id="1", page_id="p1", page_name="Marca X", keyword="joyería",
        sector="joyeria", source="api",
    )
    defaults.update(kwargs)
    return Ad(**defaults)


def test_aggregate_groups_by_page_id():
    ads = [make_ad(ad_id="1", page_id="p1"), make_ad(ad_id="2", page_id="p1"),
           make_ad(ad_id="3", page_id="p2", page_name="Otra")]
    leads = aggregate(ads)
    assert set(leads) == {"p1", "p2"}
    assert leads["p1"].active_ads == 2
    assert leads["p2"].page_name == "Otra"


def test_aggregate_extracts_website_from_link_url():
    ads = [make_ad(link_urls=["https://www.mimarca.es/producto"])]
    leads = aggregate(ads)
    assert leads["p1"].website == "https://mimarca.es"


def test_aggregate_ignores_social_platform_domains():
    ads = [make_ad(link_urls=["https://www.instagram.com/mimarca"],
                    bodies=["Síguenos en instagram.com/mimarca"])]
    leads = aggregate(ads)
    assert leads["p1"].website == ""


def test_aggregate_finds_domain_in_body_text_as_fallback():
    ads = [make_ad(bodies=["Compra en mimarca.com ahora"])]
    leads = aggregate(ads)
    assert leads["p1"].website == "https://mimarca.com"


def test_aggregate_skips_ads_without_page_id():
    ads = [make_ad(page_id="")]
    leads = aggregate(ads)
    assert leads == {}
