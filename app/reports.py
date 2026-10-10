import json
import uuid
from datetime import datetime, timedelta
from . import config
from .extract import CATEGORIES, ValidationError, extract

_session_counts = {}


def now():
    return datetime.now().replace(microsecond=0)


def segment_exists(con, sid):
    return con.execute("SELECT 1 FROM segment WHERE segment_id=?", (sid,)).fetchone() is not None


def draft(con, text, segment_id, live=None):
    if not segment_exists(con, segment_id):
        raise ValidationError("unknown_segment")
    ext, mode, err = extract(text, live) if live else extract(text)
    return {"original_text": text, "segment_id": segment_id, "extracted": ext, "extraction_mode": mode,
            "extraction_error": err, "categories": list(CATEGORIES), "persisted": False}


def submit(con, idem_key, text, segment_id, category, extraction_mode, extraction_confidence=None,
           session=None, photo_path=None):
    if not idem_key:
        raise ValidationError("missing_idempotency_key")
    existing = con.execute("SELECT * FROM report WHERE idempotency_key=?", (idem_key,)).fetchone()
    if existing:
        return dict(existing), False
    if category not in CATEGORIES:
        raise ValidationError("bad_category")
    if extraction_mode not in ("live", "replay", "manual"):
        raise ValidationError("bad_mode")
    if not segment_exists(con, segment_id):
        raise ValidationError("unknown_segment")
    if session:
        _session_counts[session] = _session_counts.get(session, 0) + 1
        if _session_counts[session] > config.SESSION_REPORT_CAP:
            raise ValidationError("session_cap")
    rid = "R-" + uuid.uuid4().hex[:8]
    con.execute("INSERT INTO report VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, idem_key, segment_id, text, photo_path, json.dumps({"category": category}),
                 extraction_confidence, extraction_mode, "accepted", now().isoformat(), None, None, None))
    con.commit()
    return dict(con.execute("SELECT * FROM report WHERE report_id=?", (rid,)).fetchone()), True


def _get(con, rid, states):
    r = con.execute("SELECT * FROM report WHERE report_id=?", (rid,)).fetchone()
    if not r:
        raise ValidationError("unknown_report")
    if r["state"] not in states:
        raise ValidationError(f"bad_state:{r['state']}")
    return r


def _event(con, sids, field, value, etype, start, end, reviewer, supersedes=None):
    eid = "E-" + uuid.uuid4().hex[:8]
    con.execute("INSERT INTO condition_event VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                (eid, json.dumps(sids), field, value, etype, start.isoformat(),
                 end.isoformat() if end else None, "reviewed_observation", reviewer, supersedes))
    return eid


def physical_edge_fragments(con, sid):
    edge = sid.rsplit("-", 1)[0]
    rows = con.execute("SELECT segment_id FROM segment WHERE segment_id LIKE ? ORDER BY segment_id", (edge + "-%",)).fetchall()
    return [x[0] for x in rows if x[0].rsplit("-", 1)[0] == edge] or [sid]


def verify(con, rid, reviewer, starts_at=None, segment_ids=None):
    r = _get(con, rid, ("accepted",))
    cat = CATEGORIES[json.loads(r["extracted_json"])["category"]]
    sids = segment_ids or physical_edge_fragments(con, r["segment_id"])
    for sid in sids:
        if not segment_exists(con, sid):
            raise ValidationError("unknown_segment")
    start = starts_at or now()
    eid = _event(con, sids, cat["field"], cat["new_value"], cat["event_type"], start,
                 start + timedelta(hours=cat["hours"]), reviewer)
    con.execute("UPDATE report SET state='verified', reviewed_by=?, reviewed_at=?, linked_event_id=? WHERE report_id=?",
                (reviewer, now().isoformat(), eid, rid))
    con.commit()
    return eid


def repair(con, rid, reviewer, starts_at=None):
    r = _get(con, rid, ("verified",))
    ev = con.execute("SELECT * FROM condition_event WHERE event_id=?", (r["linked_event_id"],)).fetchone()
    eid = _event(con, json.loads(ev["segment_ids"]), None, None, "repair", starts_at or now(), None, reviewer,
                 ev["event_id"])
    con.execute("UPDATE report SET state='fixed', reviewed_by=?, reviewed_at=? WHERE report_id=?",
                (reviewer, now().isoformat(), rid))
    con.commit()
    return eid


def reject(con, rid, reviewer):
    _get(con, rid, ("accepted",))
    con.execute("UPDATE report SET state='rejected', reviewed_by=?, reviewed_at=? WHERE report_id=?",
                (reviewer, now().isoformat(), rid))
    con.commit()


def rollback(con, event_id, reviewer):
    ev = con.execute("SELECT * FROM condition_event WHERE event_id=?", (event_id,)).fetchone()
    if not ev or ev["rolled_back"]:
        raise ValidationError("unknown_or_already_rolled_back")
    con.execute("UPDATE condition_event SET rolled_back=1 WHERE event_id=?", (event_id,))
    if ev["event_type"] == "repair":
        con.execute("UPDATE report SET state='verified' WHERE linked_event_id=?", (ev["supersedes"],))
    else:
        con.execute("UPDATE report SET state='accepted', linked_event_id=NULL WHERE linked_event_id=?", (event_id,))
    con.commit()


def list_reports(con):
    rows = [dict(r) for r in con.execute("SELECT * FROM report ORDER BY submitted_at DESC")]
    counts = {}
    for r in rows:
        counts[r["segment_id"]] = counts.get(r["segment_id"], 0) + 1
    for r in rows:
        r["reports_on_segment"] = counts[r["segment_id"]]
        r["category"] = json.loads(r["extracted_json"])["category"]
    return rows


def list_events(con):
    return [dict(r) for r in con.execute("SELECT * FROM condition_event ORDER BY starts_at DESC")]
