import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import config, db, reports, ticket, places
from .conditions import build_net, segment_detail, scenario_departure, plan_with_reasons
from .extract import ValidationError
from .graph import load_segments, nearest_node, components
from .route import plan

app = FastAPI(title="Fear-Free Night Navigator")
STATIC = config.ROOT / "static"
con = db.connect()
SEGMENTS = load_segments()
SEG_INDEX = {s["segment_id"]: i for i, s in enumerate(SEGMENTS)}
MAIN_COMPONENT = set(components(SEGMENTS)[0])
BASE_DATE = json.loads(config.SCENARIO.read_text())["base_date"]


def auth(token):
    if token != f"Bearer {config.REVIEWER_TOKEN}":
        raise HTTPException(401, "reviewer auth required (demo bearer token)")


def depart_at(hour, minute=0):
    return scenario_departure(BASE_DATE, hour, minute)


class RouteReq(BaseModel):
    start: list[float]
    end: list[float]
    hour: int = 22
    minute: int = 0
    detour: float = config.DETOUR_FACTOR


class DraftReq(BaseModel):
    text: str
    segment_id: str


class SubmitReq(BaseModel):
    idempotency_key: str
    text: str
    segment_id: str
    category: str
    extraction_mode: str
    extraction_confidence: Optional[float] = None
    session: Optional[str] = None


class ReviewReq(BaseModel):
    report_id: str
    hour: Optional[int] = None


class RollbackReq(BaseModel):
    event_id: str


@app.get("/api/health")
def health():
    return {"ok": True, "segments": len(SEGMENTS)}


@app.get("/api/config")
def get_config():
    return {"tau": config.TAU, "r_m": config.R_M, "delta_m": config.DELTA_M, "detour": config.DETOUR_FACTOR,
            "base_date": BASE_DATE, "unknown_counts_as_concerning": True}


@app.get("/api/network")
def network(hour: int = 22):
    net = build_net(con, SEGMENTS, depart_at(hour))
    return {"segments": [{"id": s["segment_id"], "ll": s["lonlat"], "r": round(net.risk[i], 3),
                          "st": net.status[i], "closed": s["segment_id"] in net.closed}
                         for i, s in enumerate(SEGMENTS)]}


def _card(net, c):
    out = {k: v for k, v in c.items() if k not in ("nodes", "edges")}
    out["geometry"] = [{"id": SEGMENTS[e]["segment_id"], "ll": SEGMENTS[e]["lonlat"], "r": round(net.risk[e], 3),
                        "st": net.status[e], "conc": net.conc[e]} for e in c["edges"]]
    return out


@app.post("/api/route")
def route(req: RouteReq):
    dep = depart_at(req.hour, req.minute)
    s = nearest_node(SEGMENTS, req.start[0], req.start[1], MAIN_COMPONENT)
    t = nearest_node(SEGMENTS, req.end[0], req.end[1], MAIN_COMPONENT)
    net, res = plan_with_reasons(con, SEGMENTS, dep, s, t, req.detour)
    res["cards"] = [_card(net, c) for c in res["cards"]]
    res.update(departure=dep.isoformat(), snapshot="departure-time snapshot", conditions="simulated")
    a, b = _snap(req.start[0], req.start[1]), _snap(req.end[0], req.end[1])
    res["distances"] = {
        "straight_line_m": round(_metres(req.start[0], req.start[1], req.end[0], req.end[1]), 1),
        "start_to_road_m": a["distance_m"], "end_to_road_m": b["distance_m"],
    }
    return res


@app.get("/api/segment/{sid}")
def segment(sid: str, hour: int = 22):
    if sid not in SEG_INDEX:
        raise HTTPException(404, "unknown segment")
    net = build_net(con, SEGMENTS, depart_at(hour))
    i = SEG_INDEX[sid]
    return {"segment_id": sid, "risk": net.risk[i], "status": net.status[i], "coverage": net.coverage[i],
            "length_m": SEGMENTS[i]["length_m"], "parent_way_id": SEGMENTS[i]["parent_way_id"],
            "access": SEGMENTS[i]["pedestrian_access"], "closed": sid in net.closed,
            "events": net.events.get(i, []), "fields": segment_detail(net, sid)}


def guarded(fn):
    try:
        return fn()
    except ValidationError as e:
        raise HTTPException(400, str(e))


@app.post("/api/report/draft")
def report_draft(req: DraftReq):
    return guarded(lambda: reports.draft(con, req.text, req.segment_id))


@app.post("/api/report/submit")
def report_submit(req: SubmitReq):
    def go():
        r, created = reports.submit(con, req.idempotency_key, req.text, req.segment_id, req.category,
                                    req.extraction_mode, req.extraction_confidence, req.session)
        return {"report": r, "created": created}
    return guarded(go)


@app.get("/api/review/reports")
def review_list(authorization: str = Header(None)):
    auth(authorization)
    return {"reports": reports.list_reports(con), "events": reports.list_events(con)}


def _when(req):
    return depart_at(req.hour) if req.hour is not None else None


@app.post("/api/review/verify")
def review_verify(req: ReviewReq, authorization: str = Header(None)):
    auth(authorization)
    return guarded(lambda: {"event_id": reports.verify(con, req.report_id, "demo_reviewer", _when(req))})


@app.post("/api/review/repair")
def review_repair(req: ReviewReq, authorization: str = Header(None)):
    auth(authorization)
    return guarded(lambda: {"event_id": reports.repair(con, req.report_id, "demo_reviewer", _when(req))})


@app.post("/api/review/reject")
def review_reject(req: ReviewReq, authorization: str = Header(None)):
    auth(authorization)
    return guarded(lambda: reports.reject(con, req.report_id, "demo_reviewer") or {"ok": True})


@app.post("/api/review/rollback")
def review_rollback(req: RollbackReq, authorization: str = Header(None)):
    auth(authorization)
    return guarded(lambda: reports.rollback(con, req.event_id, "demo_reviewer") or {"ok": True})


class TicketReq(BaseModel):
    report_id: str


def demo_route_segments():
    path = config.DATA / "demo_pairs.json"
    if not path.exists():
        return []
    out = []
    for p in json.loads(path.read_text())["pairs"]:
        dep = depart_at(p["hour"])
        s = nearest_node(SEGMENTS, p["start"][0], p["start"][1], MAIN_COMPONENT)
        t = nearest_node(SEGMENTS, p["end"][0], p["end"][1], MAIN_COMPONENT)
        _, res = plan_with_reasons(con, SEGMENTS, dep, s, t)
        out.extend(c["segment_ids"] for c in res["cards"])
    return out


@app.post("/api/review/ticket")
def review_ticket(req: TicketReq, authorization: str = Header(None)):
    auth(authorization)
    return guarded(lambda: ticket.draft_ticket(con, req.report_id, demo_route_segments(),
                                               {s["segment_id"]: s for s in SEGMENTS}))


def _metres(la1, lo1, la2, lo2):
    import math
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def _snap(lat, lon):
    from .graph import node_coords
    n = nearest_node(SEGMENTS, lat, lon, MAIN_COMPONENT)
    la, lo = node_coords(SEGMENTS)[n]
    return {"lat": la, "lon": lo, "distance_m": round(_metres(lat, lon, la, lo), 1)}


@app.get("/api/places/search")
def places_search(q: str = "", limit: int = 8):
    res = places.search(q, limit)
    for p in res["results"]:
        p["snapped"] = _snap(p["lat"], p["lon"])
    res["bbox"] = list(places.BBOX)
    return res


@app.get("/api/places")
def places_all():
    items = [dict(p) for p in places.local_places()]
    for p in items:
        p["snapped"] = _snap(p["lat"], p["lon"])
    return {"count": len(items), "source": "osm_tiles", "places": items,
            "attribution": "Data (c) OpenStreetMap contributors, ODbL."}


@app.get("/api/demo_pairs")
def demo_pairs():
    path = config.DATA / "demo_pairs.json"
    if not path.exists():
        raise HTTPException(503, "demo pairs unavailable: data/demo_pairs.json is missing; run python scripts/demo_gate.py")
    return json.loads(path.read_text())


@app.get("/api/provenance")
def provenance():
    return {"actual_source_v1": "synthetic_generator",
            "catalog": [dict(r) for r in con.execute("SELECT * FROM collection_catalog")]}


@app.get("/portal")
def portal():
    return FileResponse(STATIC / "portal.html")


@app.get("/provenance")
def provenance_page():
    return FileResponse(STATIC / "provenance.html")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
