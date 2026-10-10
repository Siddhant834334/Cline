import heapq
import math
from itertools import count
from . import config
from .graph import adjacency


class Net:
    def __init__(self, segments, risk, status, coverage=None, closed=frozenset(), events=None,
                 tau=config.TAU, r_m=config.R_M, delta=config.DELTA_M):
        self.segs = segments
        self.risk = risk
        self.status = status
        self.coverage = coverage
        self.closed = set(closed)
        self.adj = adjacency(segments, self.closed)
        self.events = events or {}
        self.tau, self.r_m, self.delta = tau, r_m, delta
        self.conc = [status[i] == "no_data" or risk[i] > tau for i in range(len(segments))]


def _rebuild(parent, key):
    nodes, edges = [], []
    while key is not None:
        prev, eidx = parent[key]
        nodes.append(key[0])
        if eidx is not None:
            edges.append(eidx)
        key = prev
    return nodes[::-1], edges[::-1]


def fastest(net, s, t):
    dist, parent = {s: 0.0}, {(s,): (None, None)}
    heap = [(0.0, s)]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, math.inf):
            continue
        if n == t:
            return _rebuild(parent, (t,)) + (d,)
        for m, e in net.adj.get(n, ()):
            nd = d + net.segs[e]["walk_time_s"]
            if nd < dist.get(m, math.inf):
                dist[m] = nd
                parent[(m,)] = ((n,), e)
                heapq.heappush(heap, (nd, m))
    return None


def _step(net, c, g, e, L):
    ln = net.segs[e]["length_m"]
    if net.conc[e]:
        c2 = c + ln
        return None if c2 > L + 1e-6 else (c2, 0.0)
    if c == 0.0:
        return (0.0, 0.0)
    g2 = g + ln
    if g2 >= net.r_m - 1e-6:
        return (0.0, 0.0)
    return (c, g2)


def _key(net, n, c, g):
    return (n, math.ceil(c / net.delta - 1e-6), math.floor(g / net.delta + 1e-6))


def product_search(net, s, t, L, budget, objective="time"):
    tie = count()
    start = (s, 0, 0)
    best = {start: (0.0, 0.0)}
    parent = {start: (None, None)}
    heap = [((0.0, 0.0), next(tie), start, 0.0, 0.0, 0.0, 0.0)]
    settled = set()
    while heap:
        _, _, key, c, g, tm, ex = heapq.heappop(heap)
        if key in settled:
            continue
        settled.add(key)
        n = key[0]
        if n == t:
            nodes, edges = _rebuild(parent, key)
            return nodes, edges, tm
        for m, e in net.adj.get(n, ()):
            st = _step(net, c, g, e, L)
            if st is None:
                continue
            seg = net.segs[e]
            tm2 = tm + seg["walk_time_s"]
            if tm2 > budget + 1e-6:
                continue
            ex2 = ex + (seg["length_m"] if net.conc[e] else 0.0)
            k2 = _key(net, m, *st)
            if k2 in settled:
                continue
            p2 = (tm2, ex2) if objective == "time" else (ex2, tm2)
            if p2 < best.get(k2, (math.inf, math.inf)):
                best[k2] = p2
                parent[k2] = (key, e)
                heapq.heappush(heap, (p2, next(tie), k2, st[0], st[1], tm2, ex2))
    return None


def longest_run(net, edges):
    c = g = longest = 0.0
    for e in edges:
        ln = net.segs[e]["length_m"]
        if net.conc[e]:
            c += ln
            g = 0.0
            longest = max(longest, c)
        elif c > 0.0:
            g += ln
            if g >= net.r_m - 1e-9:
                c = g = 0.0
    return longest


def metrics(net, nodes, edges):
    segs = net.segs
    length = sum(segs[e]["length_m"] for e in edges)
    tm = sum(segs[e]["walk_time_s"] for e in edges)
    conc_m = sum(segs[e]["length_m"] for e in edges if net.conc[e])
    unk_m = sum(segs[e]["length_m"] for e in edges if net.status[e] == "no_data")
    lr = longest_run(net, edges)
    sp = config.WALK_SPEED_MPS
    cov = None
    if net.coverage is not None and length:
        cov = sum(net.coverage[e] * segs[e]["length_m"] for e in edges) / length
    return {
        "time_s": tm, "length_m": length,
        "concerning_m": conc_m, "concerning_min": conc_m / sp / 60,
        "longest_stretch_m": lr, "longest_stretch_min": lr / sp / 60,
        "max_segment_risk": max((net.risk[e] for e in edges), default=0.0),
        "unknown_m": unk_m, "coverage": cov,
        "revisits_node": len(nodes) != len(set(nodes)),
        "segment_ids": [segs[e]["segment_id"] for e in edges],
        "nodes": nodes, "edges": edges,
    }


def _shared(a, b, segs):
    sb = set(b["edges"])
    common = sum(segs[e]["length_m"] for e in a["edges"] if e in sb)
    return common / (min(a["length_m"], b["length_m"]) or 1.0)


def _reasons(net, card, fast):
    codes = ["FASTEST"] if card is fast else []
    if card["longest_stretch_m"] < fast["longest_stretch_m"] - 1e-6:
        codes.append("SHORTER_LONGEST_STRETCH")
    if card["concerning_m"] < fast["concerning_m"] - 1e-6:
        codes.append("LESS_CONCERNING_EXPOSURE")
    if card["unknown_m"] > 0:
        codes.append("CONTAINS_NO_DATA")
    mine = set(card["edges"])
    for e in fast["edges"]:
        if e not in mine:
            for ev in net.events.get(e, ()):
                if f"AVOIDS_EVENT:{ev}" not in codes:
                    codes.append(f"AVOIDS_EVENT:{ev}")
    for e in card["edges"]:
        for ev in net.events.get(e, ()):
            if f"PASSES_EVENT:{ev}" not in codes:
                codes.append(f"PASSES_EVENT:{ev}")
    return codes


def plan(net, s, t, detour=config.DETOUR_FACTOR, l_cap=config.L_CAP_M):
    if s not in net.adj or t not in net.adj:
        return {"status": "unreachable", "reason": "endpoint_not_on_eligible_graph", "cards": []}
    fr = fastest(net, s, t)
    if fr is None:
        return {"status": "unreachable", "reason": "no_path_in_eligible_graph", "cards": []}
    fnodes, fedges, ftime = fr
    budget = ftime * detour
    fast = metrics(net, fnodes, fedges)
    fast.update(name="fastest", claim="exact fastest eligible")
    hi = min(l_cap, math.ceil(fast["longest_stretch_m"] / net.delta - 1e-6) * net.delta)
    grid = [i * net.delta for i in range(int(round(hi / net.delta)) + 1)]
    lo_i, hi_i, best = 0, len(grid) - 1, None
    while lo_i <= hi_i:
        mid = (lo_i + hi_i) // 2
        r = product_search(net, s, t, grid[mid], budget, "time")
        if r is not None:
            best, hi_i = (grid[mid], r), mid - 1
        else:
            lo_i = mid + 1
    cards, l_star = [fast], None
    if best is not None:
        l_star, (cn, ce, _) = best
        calm = metrics(net, cn, ce)
        calm.update(name="calmest", l_bound_m=l_star,
                    claim=f"minimal longest continuous stretch within budget, to {net.delta:g} m buckets")
        cards.append(calm)
        br = product_search(net, s, t, l_star, budget, "exposure")
        if br is not None:
            bal = metrics(net, br[0], br[1])
            bal.update(name="balanced", claim="best among generated candidates")
            cards.append(bal)
    out, dropped = [], []
    for c in cards:
        if c["time_s"] > budget + 1e-6:
            dropped.append({"name": c["name"], "why": "over_budget"})
            continue
        if c["revisits_node"]:
            dropped.append({"name": c["name"], "why": "revisits_node"})
            continue
        dup = next((o for o in out if _shared(c, o, net.segs) > config.DEDUP_SHARE), None)
        if dup:
            dup.setdefault("also", []).append(c["name"])
            continue
        out.append(c)
    for c in out:
        c["reason_codes"] = _reasons(net, c, fast)
    return {"status": "ok", "budget_s": budget, "l_star_m": l_star, "cards": out, "dropped": dropped,
            "tau": net.tau, "r_m": net.r_m, "delta_m": net.delta}
