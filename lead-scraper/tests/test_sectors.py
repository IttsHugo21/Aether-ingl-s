from leads.sectors import build_queries, load_blocklist, load_sectors


def test_load_sectors_has_expected_keys():
    sectors = load_sectors()
    for key in ["joyeria", "cosmetica", "moda", "calzado", "accesorios", "hogar",
                "deporte", "mascotas", "alimentacion", "electronica"]:
        assert key in sectors
        assert sectors[key]["keywords"]


def test_build_queries_all_sectors_no_duplicates():
    sectors = load_sectors()
    queries = build_queries(sectors, None, [])
    keywords = [kw for _, kw in queries]
    assert len(keywords) == len(set(k.lower() for k in keywords))
    assert len(queries) > 50


def test_build_queries_selected_subset():
    sectors = load_sectors()
    queries = build_queries(sectors, ["joyeria"], [])
    assert all(s == "joyeria" for s, _ in queries)
    assert ("joyeria", "anillos") in queries


def test_build_queries_unknown_sector_raises():
    sectors = load_sectors()
    try:
        build_queries(sectors, ["no_existe"], [])
        assert False, "debería haber lanzado SystemExit"
    except SystemExit:
        pass


def test_build_queries_extra_keywords():
    sectors = load_sectors()
    queries = build_queries(sectors, ["joyeria"], ["algo muy raro"])
    assert ("custom", "algo muy raro") in queries


def test_blocklist_loaded_and_lowercase():
    blocklist = load_blocklist()
    assert "amazon" in blocklist
    assert all(term == term.lower() for term in blocklist)
