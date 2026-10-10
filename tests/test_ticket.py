import json
import shutil
import sqlite3
import pytest
from fastapi.testclient import TestClient
from app import config, db, reports, ticket
from app.extract import ValidationError
from app.ticket_text import validate_bodies

AUTH = {"Authorization": f"Bearer {config.REVIEWER_TOKEN}"}


@pytest.fixture
def con(tmp_path):
    p = tmp_path / "fnn.db"
    shutil.copy(config.DB_PATH, p)
    c = db.connect(p)
    yield c
    c.close()


def verified_report(con, key="t1"):
    sid = con.execute("SELECT segment_id FROM segment LIMIT 1").fetchone()[0]
    r, _ = reports.submit(con, key, "light nahi hai", sid, "lamp_outage", "manual")
    reports.verify(con, r["report_id"], "rev")
    return r["report_id"], sid


def boom(_):
    raise RuntimeError("down")


def test_same_report_twice_yields_one_ticket(con, tmp_path):
    rid, _ = verified_report(con)
    a = ticket.draft_ticket(con, rid, llm=boom, outbox=tmp_path / "out")
    b = ticket.draft_ticket(con, rid, llm=boom, outbox=tmp_path / "out")
    assert a["ticket_id"] == b["ticket_id"]
    assert con.execute("SELECT COUNT(*) FROM ticket WHERE report_id=?", (rid,)).fetchone()[0] == 1
    saved = json.loads((tmp_path / "out" / f"{rid}.json").read_text())
    assert saved["ticket_id"] == a["ticket_id"]


def test_delivered_stays_zero_and_disclosure_present(con, tmp_path):
    rid, _ = verified_report(con)
    t = ticket.draft_ticket(con, rid, llm=boom, outbox=tmp_path)
    assert t["delivered"] == 0
    assert t["disclosure"] == "demo outbox - not delivered to any authority"
    assert t["drafted_by"].startswith("cline-authored module (SDK integration not run)")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE ticket SET delivered=1 WHERE report_id=?", (rid,))
    for k in ("ticket_id", "segment_id", "parent_way_id", "category", "location", "outage_duration_hours",
              "affected_route_count", "body_en", "body_hi", "drafted_by", "delivered"):
        assert k in t


@pytest.mark.parametrize("bad", [
    {"body_en": "x"},
    {"body_en": "x", "body_hi": "only latin", },
    {"body_en": "x", "body_hi": "हिंदी", "extra": "y"},
    {"body_en": "", "body_hi": "हिंदी"},
    {"body_en": 5, "body_hi": "हिंदी"},
    {"body_en": "x" * 5000, "body_hi": "हिंदी"},
    "not a dict",
])
def test_malformed_agent_output_rejected(bad):
    with pytest.raises(ValidationError):
        validate_bodies(bad)


def test_malformed_llm_output_never_stored(con, tmp_path):
    rid, _ = verified_report(con)
    t = ticket.draft_ticket(con, rid, llm=lambda f: {"body_en": "ignore previous", "body_hi": "latin only"},
                            outbox=tmp_path)
    assert t["body_hi"] != "latin only"
    assert t["drafted_by"].endswith("deterministic template text")


def test_valid_llm_output_used(con, tmp_path):
    rid, _ = verified_report(con)
    t = ticket.draft_ticket(con, rid, llm=lambda f: {"body_en": "Lamp out.", "body_hi": "लाइट खराब है।"},
                            outbox=tmp_path)
    assert t["body_en"] == "Lamp out." and t["drafted_by"] == "cline-authored module (SDK integration not run)"


def test_unverified_report_rejected(con, tmp_path):
    sid = con.execute("SELECT segment_id FROM segment LIMIT 1").fetchone()[0]
    r, _ = reports.submit(con, "u1", "x", sid, "lamp_outage", "manual")
    with pytest.raises(ValidationError):
        ticket.draft_ticket(con, r["report_id"], llm=boom, outbox=tmp_path)


def test_affected_route_count():
    assert ticket.affected_route_count(["a", "b"], [["x", "a"], ["y"], ["b", "z"]]) == 2


def test_endpoint_requires_auth_and_is_idempotent(con, tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "con", con)
    monkeypatch.setattr(ticket, "OUTBOX", tmp_path / "outbox")
    monkeypatch.setattr(ticket, "LLM", boom)
    rid, _ = verified_report(con)
    c = TestClient(main.app)
    assert c.post("/api/review/ticket", json={"report_id": rid}).status_code == 401
    assert c.post("/api/review/ticket", json={"report_id": rid},
                  headers={"Authorization": "Bearer wrong"}).status_code == 401
    a = c.post("/api/review/ticket", json={"report_id": rid}, headers=AUTH)
    b = c.post("/api/review/ticket", json={"report_id": rid}, headers=AUTH)
    assert a.status_code == 200 and a.json()["ticket_id"] == b.json()["ticket_id"]
    assert a.json()["disclosure"] == "demo outbox - not delivered to any authority"
    assert a.json()["delivered"] == 0 and "drafted_by" in a.json()
    assert con.execute("SELECT COUNT(*) FROM ticket").fetchone()[0] == 1
