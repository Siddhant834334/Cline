from app import config
from app.route import Net


def seg(sid, u, v, length):
    return {"segment_id": sid, "u": u, "v": v, "edge_key": 0, "parent_way_id": sid,
            "length_m": float(length), "walk_time_s": length / config.WALK_SPEED_MPS,
            "pedestrian_access": "yes", "geometry_wkt": "", "crs": "test",
            "lonlat": [[0, 0], [0, 0]]}


def chain(prefix, start, end, pieces):
    segs, risks, prev = [], [], start
    for i, (length, risk) in enumerate(pieces):
        nxt = end if i == len(pieces) - 1 else f"{prefix}{i}"
        segs.append(seg(f"{prefix}-{i}", prev, nxt, length))
        risks.append(risk)
        prev = nxt
    return segs, risks


def counterexample():
    a_segs, a_r = chain("A", "S", "T", [(60, 0.1), (90, 0.9), (60, 0.1)])
    b_segs, b_r = chain("B", "S", "T", [(30, 0.6), (50, 0.1), (30, 0.6), (50, 0.1), (30, 0.6), (30, 0.1)])
    segs, risks = a_segs + b_segs, a_r + b_r
    return segs, risks


def make_net(segs, risks, status=None, **kw):
    status = status or ["ok"] * len(segs)
    return Net(segs, risks, status, **kw)
