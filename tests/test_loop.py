import json
import shutil
import uuid
import pytest
from app import db, reports
from app.conditions import build_net, scenario_departure, scenario_date
from app.graph import load_segments
from app.route import plan
from app.extract import extract, ValidationError
from app import config

S, T = "1359542831_11070806064_0_5", "1359543876_1359541983_0_3"
DEP = scenario_departure("2025-10-10", 22)


@pytest.fixture
def con(tmp_path):
    p = tmp_path / "fnn.db"
    shutil.copy(config.DB_PATH, p)
    c = db.connect(p)
    yield c
    c.close()


@pytest.fixture(scope="module")
def segs():
    return load_segments()


def calm(con, segs, dep=DEP):
    from app.conditions import plan_with_reasons
    _, res = plan_with_reasons(con, segs, dep, S, T)
    c = next(c for c in res["cards"] if c["name"] == "calmest" or "calmest" in c.get("also", []))
    return c


def target_segment(c, con, segs):
    return target_edge(c, con, segs)[0]


def target_edge(c, con, segs):
    from app.extract import CATEGORIES
    outage = CATEGORIES["lamp_outage"]
    net = build_net(con, segs, DEP)
    idx = {s["segment_id"]: i for i, s in enumerate(segs)}
    route = c["segment_ids"]
    on_route = {}
    for pos, sid in enumerate(route):
        on_route.setdefault(sid.rsplit("-", 1)[0], []).append(pos)
    candidates = {}
    for edge, positions in on_route.items():
        if all(net.conc[idx[route[p]]] for p in positions):
            continue
        candidates[edge] = reports.physical_edge_fragments(con, route[positions[0]])
    if not candidates:
        pytest.fail("target_edge: calmest route has no physical edge with a non-concerning fragment")
    all_frags = sorted({f for frags in candidates.values() for f in frags})
    con.execute("INSERT INTO condition_event VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                ("E-probe", json.dumps(all_frags), outage["field"], outage["new_value"], outage["event_type"],
                 DEP.replace(hour=21).isoformat(), DEP.replace(hour=23).isoformat(), "reviewed_observation",
                 "test_probe", None))
    try:
        probe = build_net(con, segs, DEP)
    finally:
        con.rollback()
    qualified = []
    for edge, frags in candidates.items():
        if not all(probe.risk[idx[f]] > probe.tau for f in frags):
            continue
        positions = on_route[edge]
        lo, hi = min(positions), max(positions)
        adjacent = (lo > 0 and net.conc[idx[route[lo - 1]]]) or (hi + 1 < len(route) and net.conc[idx[route[hi + 1]]])
        length = sum(segs[idx[route[p]]]["length_m"] for p in positions)
        qualified.append((adjacent, length, edge))
    if not qualified:
        pytest.fail(f"target_edge: none of {len(candidates)} candidate edges on the calmest route would have every "
                    f"fragment above TAU={net.tau} after a lamp_outage (lighting_level={outage['new_value']}); "
                    "the scenario gives no segment a lamp outage can make concerning")
    qualified.sort(key=lambda q: (q[0], q[1]), reverse=True)
    edge = qualified[0][2]
    return [route[p] for p in on_route[edge]]


def test_loop_unverified_noop_verify_reroutes_repair_restores_rollback(con, segs):
    before = calm(con, segs)
    edge = target_edge(before, con, segs)
    sid = edge[0]
    r, created = reports.submit(con, "k1", "light nahi hai", sid, "lamp_outage", "manual")
    assert created and r["state"] == "accepted"
    assert calm(con, segs)["segment_ids"] == before["segment_ids"]
    eid = reports.verify(con, r["report_id"], "rev", starts_at=DEP.replace(hour=21))
    stored = json.loads(con.execute("SELECT segment_ids FROM condition_event WHERE event_id=?", (eid,)).fetchone()[0])
    assert set(edge) <= set(stored) and all(x.rsplit("-", 1)[0] == edge[0].rsplit("-", 1)[0] for x in stored)
    after = calm(con, segs)
    assert after["segment_ids"] != before["segment_ids"]
    assert sid not in after["segment_ids"]
    assert f"AVOIDS_EVENT:{eid}" in after["reason_codes"]
    state = con.execute("SELECT state FROM report WHERE report_id=?", (r["report_id"],)).fetchone()[0]
    assert state == "verified"
    rep = reports.repair(con, r["report_id"], "rev", starts_at=DEP.replace(hour=21, minute=30))
    assert calm(con, segs)["segment_ids"] == before["segment_ids"]
    assert con.execute("SELECT state FROM report WHERE report_id=?", (r["report_id"],)).fetchone()[0] == "fixed"
    reports.rollback(con, rep, "rev")
    assert sid not in calm(con, segs)["segment_ids"]
    reports.rollback(con, eid, "rev")
    assert calm(con, segs)["segment_ids"] == before["segment_ids"]


def test_event_expires(con, segs):
    before = calm(con, segs)
    sid = target_segment(before, con, segs)
    r, _ = reports.submit(con, "k2", "x", sid, "lamp_outage", "manual")
    reports.verify(con, r["report_id"], "rev", starts_at=DEP.replace(day=1))
    assert calm(con, segs)["segment_ids"] == before["segment_ids"]


def test_idempotency(con):
    sid = con.execute("SELECT segment_id FROM segment LIMIT 1").fetchone()[0]
    a, c1 = reports.submit(con, "same", "t", sid, "lamp_outage", "manual")
    b, c2 = reports.submit(con, "same", "t", sid, "lamp_outage", "manual")
    assert c1 and not c2 and a["report_id"] == b["report_id"]
    assert con.execute("SELECT COUNT(*) FROM report").fetchone()[0] == 1


def test_validation_outside_llm(con):
    with pytest.raises(ValidationError):
        reports.submit(con, "z", "t", "not-a-segment", "lamp_outage", "manual")
    sid = con.execute("SELECT segment_id FROM segment LIMIT 1").fetchone()[0]
    with pytest.raises(ValidationError):
        reports.submit(con, "z2", "t", sid, "ghosts", "manual")


def test_llm_failure_keeps_manual_and_text(con):
    def boom(_):
        raise RuntimeError("down")
    sid = con.execute("SELECT segment_id FROM segment LIMIT 1").fetchone()[0]
    d = reports.draft(con, "kuch ajeeb text", sid, live=boom)
    assert d["extraction_mode"] == "manual" and d["original_text"] == "kuch ajeeb text"
    assert "lamp_outage" in d["categories"] and d["persisted"] is False
    d2 = reports.draft(con, "Hostel ke paas wali road pe light nahi hai, bahut andhera hai", sid, live=boom)
    assert d2["extraction_mode"] == "replay" and d2["extracted"]["category"] == "lamp_outage"
    assert con.execute("SELECT COUNT(*) FROM report").fetchone()[0] == 0


def test_llm_bad_output_rejected():
    ext, mode, _ = extract("x", live=lambda t: {"category": "DROP TABLE", "extraction_confidence": 5})
    assert mode == "manual" and ext is None


def test_one_field_swap_changes_routes_without_code_change(con, segs):
    before = calm(con, segs)
    net = build_net(con, segs, DEP)
    idx = {s["segment_id"]: i for i, s in enumerate(segs)}
    swap = [sid for sid in before["segment_ids"] if not net.conc[idx[sid]]][:20]
    rows = [(sid, "lighting_level", 0.0, 22, "reviewed_observation", DEP.replace(hour=20).isoformat(),
             DEP.replace(hour=23, minute=59).isoformat(), "verified", "swap") for sid in swap]
    con.executemany("INSERT INTO observation(segment_id,field,value,hour_of_day,source,observed_at,valid_until,review_status,scenario_version) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    net2 = build_net(con, segs, DEP)
    assert net2.field_table[swap[0]]["lighting_level"]["source"] == "reviewed_observation"
    assert calm(con, segs)["segment_ids"] != before["segment_ids"]


def test_midnight_trip_uses_correct_scenario_date():
    late = scenario_departure("2025-10-10", 0, 30)
    assert late.isoformat().startswith("2025-10-11T00:30")
    assert scenario_date(late) == "2025-10-10"
    assert scenario_date(scenario_departure("2025-10-10", 23, 50)) == "2025-10-10"
