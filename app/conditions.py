import json
from datetime import datetime, timedelta
from . import config
from .score import segment_risk, parse_ts
from .route import Net

SOURCE_RANK = {"reviewed_observation": 3, "scenario_event": 2, "synthetic_generator": 1}


def scenario_hour(depart):
    return depart.hour


def scenario_date(depart):
    d = depart if depart.hour >= 12 else depart - timedelta(days=1)
    return d.date().isoformat()


def scenario_departure(base_date, hour, minute=0):
    base = datetime.fromisoformat(base_date + "T00:00:00")
    day = base if hour >= 12 else base + timedelta(days=1)
    return day.replace(hour=hour, minute=minute)


def active_events(con, at):
    rows = con.execute("SELECT * FROM condition_event WHERE rolled_back=0").fetchall()
    out = []
    superseded = {r["supersedes"] for r in rows if r["supersedes"] and parse_ts(r["starts_at"]) <= at}
    for r in rows:
        if r["event_id"] in superseded:
            continue
        if parse_ts(r["starts_at"]) <= at and (r["ends_at"] is None or at < parse_ts(r["ends_at"])):
            out.append(dict(r))
    return out


def field_table(con, hour, at):
    rows = con.execute(
        "SELECT segment_id, field, value, source, observed_at, valid_until, review_status FROM observation "
        "WHERE hour_of_day=? AND source != 'community_report'", (hour,)).fetchall()
    table = {}
    for r in rows:
        if r["valid_until"] and parse_ts(r["valid_until"]) < at:
            continue
        cur = table.setdefault(r["segment_id"], {}).get(r["field"])
        rank = SOURCE_RANK.get(r["source"], 0)
        if cur is None or rank > SOURCE_RANK.get(cur["source"], 0) or (rank == SOURCE_RANK.get(cur["source"], 0) and r["observed_at"] > cur["observed_at"]):
            table[r["segment_id"]][r["field"]] = dict(r)
    return table


def build_net(con, segments, depart, tau=config.TAU, r_m=config.R_M, delta=config.DELTA_M, with_events=True):
    hour = scenario_hour(depart)
    table = field_table(con, hour, depart)
    events = active_events(con, depart) if with_events else []
    overrides, closed, ev_by_seg = {}, set(), {}
    for ev in events:
        if ev["event_type"] == "repair":
            continue
        sids = json.loads(ev["segment_ids"])
        for sid in sids:
            ev_by_seg.setdefault(sid, []).append(ev["event_id"])
            if ev["event_type"] in ("closure",):
                closed.add(sid)
            elif ev["field"]:
                overrides.setdefault(sid, {})[ev["field"]] = ev
    risk, status, cov = [], [], []
    idx = {s["segment_id"]: i for i, s in enumerate(segments)}
    for s in segments:
        sid = s["segment_id"]
        f = table.get(sid, {})
        obs = {k: (f[k]["value"] if k in f else None) for k in config.WEIGHTS}
        ats = [parse_ts(v["observed_at"]) for v in f.values()]
        for k, ev in overrides.get(sid, {}).items():
            obs[k] = ev["new_value"]
        obs["_observed_at"] = min(ats) if ats else None
        r, c, st = segment_risk(obs, now=depart)
        risk.append(r)
        status.append(st)
        cov.append(c)
    events_idx = {idx[sid]: v for sid, v in ev_by_seg.items() if sid in idx}
    net = Net(segments, risk, status, coverage=cov, closed=closed, events=events_idx, tau=tau, r_m=r_m, delta=delta)
    net.field_table = table
    net.overrides = overrides
    return net


def segment_detail(net, sid):
    f = net.field_table.get(sid, {})
    ov = net.overrides.get(sid, {})
    fields = []
    for k in config.WEIGHTS:
        if k in ov:
            ev = ov[k]
            fields.append({"field": k, "value": ev["new_value"], "source": ev["source"], "observed_at": ev["starts_at"],
                           "valid_until": ev["ends_at"], "review_status": "verified", "event_id": ev["event_id"]})
        elif k in f:
            r = f[k]
            fields.append({"field": k, "value": r["value"], "source": r["source"], "observed_at": r["observed_at"],
                           "valid_until": r["valid_until"], "review_status": r["review_status"]})
        else:
            fields.append({"field": k, "value": None, "source": None, "missing": True})
    return fields


def plan_with_reasons(con, segments, depart, s, t, detour=config.DETOUR_FACTOR):
    from .route import plan, add_event_reasons
    net = build_net(con, segments, depart)
    res = plan(net, s, t, detour=detour)
    if net.events:
        add_event_reasons(res, plan(build_net(con, segments, depart, with_events=False), s, t, detour=detour), net)
    return net, res
