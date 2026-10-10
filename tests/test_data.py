import sqlite3
from app import db
from app.catalog import CATALOG, check_catalog
from app.generate import generate, rows_digest, DEFAULT_SCENARIO
from app.graph import load_segments


def test_scenario_regenerates_identically():
    segs = load_segments()[:300]
    assert rows_digest(generate(segs, DEFAULT_SCENARIO)) == rows_digest(generate(segs, DEFAULT_SCENARIO))


def test_some_fields_missing():
    segs = load_segments()[:500]
    rows = generate(segs, DEFAULT_SCENARIO)
    per = {}
    for r in rows:
        if r[4] == "synthetic_generator" and r[3] == 22:
            per.setdefault(r[0], set()).add(r[1])
    assert any(len(v) < 7 for v in per.values())
    assert len(per) < len(segs)
    assert all(r[4] in ("synthetic_generator", "community_report") for r in rows)


def test_catalog_consistency(tmp_path):
    con = db.connect(tmp_path / "t.db")
    con.executemany("INSERT INTO collection_catalog VALUES (?,?,?,?,?,?)", CATALOG)
    check_catalog(con)
    con.execute("INSERT INTO collection_catalog VALUES ('cctv2','x','measurement','institutional','x','unchecked')")
    try:
        check_catalog(con)
        assert False
    except AssertionError as e:
        assert "institutional" in str(e)


def test_demo_pairs_file_contract():
    import json
    from app import config
    d = json.loads((config.DATA / "demo_pairs.json").read_text())
    assert d["gate_status"] in ("pass", "fail")
    for k in ("concerning_pct_by_hour", "all_pairs", "dark_subset", "checks"):
        assert k in d
    assert set(d["concerning_pct_by_hour"]) == {"18", "20", "22", "01"}
    assert d["pairs"] and all({"label", "start", "end", "hour", "fastest_longest_stretch_m",
                                "calmest_longest_stretch_m"} <= set(p) for p in d["pairs"])


def test_demo_pairs_endpoint_503_when_missing(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, config
    monkeypatch.setattr(config, "DATA", tmp_path)
    r = TestClient(main.app).get("/api/demo_pairs")
    assert r.status_code == 503 and "demo_pairs.json" in r.json()["detail"]
