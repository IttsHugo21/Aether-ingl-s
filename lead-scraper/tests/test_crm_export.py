import json

from leads.crm_export import export_for_crm, lead_to_crm_doc
from leads.models import Ad, Lead


def make_lead(page_name, tier="A", score=80, excluded="", n_ads=3, website="https://x.com"):
    lead = Lead(page_id=page_name, page_name=page_name, tier=tier, score=score, excluded=excluded)
    lead.website = website
    lead.sectors = {"joyeria"}
    lead.reasons = ["motivo 1", "motivo 2"]
    for i in range(n_ads):
        lead.ads[str(i)] = Ad(ad_id=str(i), page_id=page_name, page_name=page_name,
                               keyword="k", sector="joyeria", source="api")
    return lead


def test_lead_to_crm_doc_has_expected_schema():
    lead = make_lead("Marca Ejemplo")
    doc = lead_to_crm_doc(lead, tanda=2)
    assert set(doc) == {
        "marca", "sector", "pais", "web", "anuncio_url", "num_anuncios",
        "tanda", "estado", "notas", "fecha_tanda",
    }
    assert doc["marca"] == "Marca Ejemplo"
    assert doc["tanda"] == 2
    assert doc["estado"] == "pendiente"
    assert doc["num_anuncios"] == 3
    assert doc["web"] == "https://x.com"


def test_export_for_crm_excludes_blocked_and_below_min_tier(tmp_path):
    leads = {
        "a": make_lead("Top A", tier="A", score=90),
        "b": make_lead("Mid B", tier="B", score=50),
        "c": make_lead("Low C", tier="C", score=10),
        "d": make_lead("Bloqueada", tier="A", score=99, excluded="blocklist"),
    }
    path = tmp_path / "crm.json"
    n = export_for_crm(leads, path, tanda=1, min_tier="B")
    assert n == 2
    data = json.loads(path.read_text(encoding="utf-8"))
    marcas = {d["marca"] for d in data.values()}
    assert marcas == {"Top A", "Mid B"}


def test_export_for_crm_generates_unique_doc_ids_for_same_slug(tmp_path):
    leads = {
        "a": make_lead("Marca Duplicada"),
        "b": make_lead("Marca Duplicada "),  # mismo slug tras normalizar
    }
    path = tmp_path / "crm.json"
    export_for_crm(leads, path, tanda=1)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"marca-duplicada", "marca-duplicada-2"}
