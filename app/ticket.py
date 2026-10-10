import json
import uuid
from datetime import datetime
from . import config
from .extract import ValidationError
from .ticket_text import validate_bodies, llm_bodies, template_bodies

DRAFTED_BY = "cline-authored module (SDK integration not run)"
TEMPLATE_SUFFIX = "; LLM unavailable, deterministic template text"
DISCLOSURE = "demo outbox - not delivered to any authority"
OUTBOX = config.DATA / "outbox"
LLM = llm_bodies


def affected_route_count(segment_ids, route_segment_lists):
    target = set(segment_ids)
    return sum(1 for segs in route_segment_lists if target & set(segs))


def _location(seg_row, segments_by_id):
    seg = (segments_by_id or {}).get(seg_row["segment_id"])
    if seg:
        la, lo = seg["lonlat"][len(seg["lonlat"]) // 2]
        return f"near {la:.5f}, {lo:.5f} on OSM way {seg_row['parent_way_id']}"
    return f"on OSM way {seg_row['parent_way_id']}"


def gather(con, report_id, route_segment_lists=(), segments_by_id=None, now=None):
    r = con.execute("SELECT * FROM report WHERE report_id=?", (report_id,)).fetchone()
    if not r:
        raise ValidationError("unknown_report")
    if r["state"] not in ("verified", "fixed") or not r["linked_event_id"]:
        raise ValidationError(f"report_not_verified:{r['state']}")
    ev = con.execute("SELECT * FROM condition_event WHERE event_id=?", (r["linked_event_id"],)).fetchone()
    if not ev:
        raise ValidationError("missing_event")
    seg = con.execute("SELECT * FROM segment WHERE segment_id=?", (r["segment_id"],)).fetchone()
    others = con.execute("SELECT COUNT(*) FROM report WHERE segment_id=? AND report_id!=?",
                         (r["segment_id"], report_id)).fetchone()[0]
    now = now or datetime.now()
    hours = max(0.0, (now - datetime.fromisoformat(ev["starts_at"])).total_seconds() / 3600.0)
    return {
        "report_id": report_id, "event_id": ev["event_id"], "segment_id": r["segment_id"],
        "parent_way_id": seg["parent_way_id"], "category": json.loads(r["extracted_json"])["category"],
        "location": _location(seg, segments_by_id), "outage_hours": round(hours, 1),
        "other_reports": others,
        "affected_routes": affected_route_count(json.loads(ev["segment_ids"]), route_segment_lists),
    }


def _ticket(row):
    f = json.loads(row["facts_json"])
    return {
        "ticket_id": row["ticket_id"], "report_id": row["report_id"], "event_id": row["event_id"],
        "segment_id": f["segment_id"], "parent_way_id": f["parent_way_id"], "category": f["category"],
        "location": f["location"], "outage_duration_hours": f["outage_hours"],
        "affected_route_count": f["affected_routes"], "other_reports_on_segment": f["other_reports"],
        "body_en": row["body_en"], "body_hi": row["body_hi"], "drafted_by": row["drafted_by"],
        "created_at": row["created_at"], "delivered": row["delivered"], "disclosure": DISCLOSURE,
    }


def draft_ticket(con, report_id, route_segment_lists=(), segments_by_id=None, llm=None, now=None,
                 outbox=None):
    llm = llm or LLM
    existing = con.execute("SELECT * FROM ticket WHERE report_id=?", (report_id,)).fetchone()
    if existing:
        return _ticket(existing)
    facts = gather(con, report_id, route_segment_lists, segments_by_id, now)
    drafted_by = DRAFTED_BY
    try:
        bodies = validate_bodies(llm(facts))
    except Exception:
        bodies = validate_bodies(template_bodies(facts))
        drafted_by = DRAFTED_BY + TEMPLATE_SUFFIX
    con.execute("INSERT OR IGNORE INTO ticket VALUES (?,?,?,?,?,?,?,0,?)",
                ("T-" + uuid.uuid4().hex[:8], report_id, facts["event_id"], bodies["body_en"], bodies["body_hi"],
                 drafted_by, datetime.now().replace(microsecond=0).isoformat(),
                 json.dumps(facts, ensure_ascii=False)))
    con.commit()
    ticket = _ticket(con.execute("SELECT * FROM ticket WHERE report_id=?", (report_id,)).fetchone())
    out = outbox or OUTBOX
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{report_id}.json").write_text(json.dumps(ticket, ensure_ascii=False, indent=2))
    return ticket
