from app.route import plan, longest_run
from app.score import segment_risk
from tests.fixtures import seg, chain, counterexample, make_net


def card(res, name):
    return next((c for c in res["cards"] if c["name"] == name or name in c.get("also", [])), None)


def test_counterexample_continuity_separates_routes():
    segs, risks = counterexample()
    res = plan(make_net(segs, risks), "S", "T")
    fast, calm = card(res, "fastest"), card(res, "calmest")
    assert fast["segment_ids"][0].startswith("A")
    assert calm["segment_ids"][0].startswith("B")
    assert abs(fast["concerning_m"] - calm["concerning_m"]) < 1e-6
    assert fast["longest_stretch_m"] == 90 and calm["longest_stretch_m"] == 30
    assert abs(fast["max_segment_risk"] - 0.9) < 1e-9 and abs(calm["max_segment_risk"] - 0.6) < 1e-9


def test_budget_enforced_low_risk_detour_rejected():
    a, ar = chain("A", "S", "T", [(100, 0.9)])
    b, br = chain("B", "S", "T", [(100, 0.1), (100, 0.1)])
    res = plan(make_net(a + b, ar + br), "S", "T", detour=1.4)
    for c in res["cards"]:
        assert c["time_s"] <= res["budget_s"] + 1e-6
        assert c["segment_ids"][0].startswith("A")
    res2 = plan(make_net(a + b, ar + br), "S", "T", detour=2.5)
    assert card(res2, "calmest")["segment_ids"][0].startswith("B")


def _summary(res):
    return {c["name"]: tuple(round(c[k], 6) for k in
            ("time_s", "length_m", "concerning_m", "longest_stretch_m", "max_segment_risk", "unknown_m"))
            for c in res["cards"]}


def test_subdivision_invariance():
    segs, risks = counterexample()
    base = _summary(plan(make_net(segs, risks), "S", "T"))
    i = next(k for k, s in enumerate(segs) if s["segment_id"] == "A-1")
    s0 = segs[i]
    p1 = seg("A-1a", s0["u"], "mid", 45)
    p2 = seg("A-1b", "mid", s0["v"], 45)
    segs2 = segs[:i] + [p1, p2] + segs[i + 1:]
    risks2 = risks[:i] + [risks[i], risks[i]] + risks[i + 1:]
    assert _summary(plan(make_net(segs2, risks2), "S", "T")) == base


def test_unreachable_returns_explicit_result():
    a, ar = chain("A", "S", "T", [(50, 0.1)])
    b, br = chain("B", "X", "Y", [(50, 0.1)])
    net = make_net(a + b, ar + br)
    res = plan(net, "S", "Y")
    assert res["status"] == "unreachable" and res["cards"] == []
    assert len(net.segs) == 2


def test_unknown_never_breaks_stretch():
    segs, risks = chain("A", "S", "T", [(30, 0.9), (60, 0.0), (30, 0.9)])
    net = make_net(segs, risks, status=["ok", "no_data", "ok"])
    assert longest_run(net, [0, 1, 2]) == 120


def test_good_shorter_than_R_does_not_break_but_R_does():
    segs, risks = chain("A", "S", "T", [(30, 0.9), (30, 0.1), (30, 0.9), (40, 0.1), (30, 0.9)])
    net = make_net(segs, risks)
    assert longest_run(net, [0, 1, 2, 3, 4]) == 60


def test_closed_edge_never_routed():
    a, ar = chain("A", "S", "T", [(5, 0.1)])
    b, br = chain("B", "S", "T", [(300, 0.9)])
    res = plan(make_net(a + b, ar + br, closed={"A-0"}), "S", "T")
    for c in res["cards"]:
        assert "A-0" not in c["segment_ids"]
    res2 = plan(make_net(a, ar, closed={"A-0"}), "S", "T")
    assert res2["status"] == "unreachable"


def test_all_missing_scores_no_data():
    assert segment_risk({}) == (1.0, 0.0, "no_data")


def test_no_renormalisation_over_observed():
    r, cov, st = segment_risk({"lighting_level": 1.0, "activity_level": 1.0})
    assert st == "ok" and abs(cov - 2 / 7) < 1e-9
    assert abs(r - 0.5 * 0.70) < 1e-9
