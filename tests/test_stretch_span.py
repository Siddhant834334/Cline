import pytest
from app.route import metrics, longest_run, plan
from tests.fixtures import chain, counterexample, make_net


def m_for(pieces, status=None):
    segs, risks = chain("A", "S", "T", pieces)
    net = make_net(segs, risks, status=status)
    edges = list(range(len(segs)))
    nodes = ["S"] + [s["v"] for s in segs]
    return net, metrics(net, nodes, edges)


def ids_len(net, ids):
    by = {s["segment_id"]: s for s in net.segs}
    return sum(by[i]["length_m"] for i in ids)


def assert_contiguous_in_order(ids, route_ids, m=None):
    start = route_ids.index(ids[0])
    pos = [route_ids.index(i) for i in ids]
    assert pos == sorted(pos) and pos[0] == start
    if m is not None:
        a, b = m["longest_stretch_edge_index"]
        assert pos[0] == a and pos[-1] == b
        assert [i for i in route_ids[a:b + 1] if i in set(ids)] == ids
    else:
        assert route_ids[start:start + len(ids)] == ids


def test_sum_of_ids_equals_longest_stretch():
    net, m = m_for([(50, 0.1), (60, 0.9), (70, 0.8), (50, 0.1), (40, 0.1), (20, 0.9)])
    assert abs(ids_len(net, m["longest_stretch_segment_ids"]) - m["longest_stretch_m"]) < 1e-6
    assert m["longest_stretch_m"] == 130
    assert m["longest_stretch_segment_ids"] == ["A-1", "A-2"]


def test_ids_contiguous_and_in_path_order():
    net, m = m_for([(50, 0.1), (60, 0.9), (70, 0.8), (50, 0.1)])
    assert_contiguous_in_order(m["longest_stretch_segment_ids"], m["segment_ids"])
    assert m["longest_stretch_edge_index"] == [1, 2]
    assert m["longest_stretch_bounds_m"] == [50.0, 180.0]


def test_no_data_segment_inside_run_is_one_unbroken_run():
    net, m = m_for([(40, 0.9), (60, 0.0), (40, 0.9)], status=["ok", "no_data", "ok"])
    assert m["longest_stretch_m"] == 140
    assert m["longest_stretch_segment_ids"] == ["A-0", "A-1", "A-2"]
    assert_contiguous_in_order(m["longest_stretch_segment_ids"], m["segment_ids"])
    assert m["longest_stretch_bounds_m"] == [0.0, 140.0]


def test_30m_good_does_not_break_but_40m_does():
    net, m = m_for([(50, 0.9), (30, 0.1), (50, 0.9)])
    assert m["longest_stretch_m"] == 100
    assert m["longest_stretch_segment_ids"] == ["A-0", "A-2"]
    assert m["longest_stretch_edge_index"] == [0, 2]
    assert m["longest_stretch_bounds_m"] == [0.0, 130.0]
    assert_contiguous_in_order(m["longest_stretch_segment_ids"], m["segment_ids"], m)
    assert abs(ids_len(net, m["longest_stretch_segment_ids"]) - m["longest_stretch_m"]) < 1e-6

    net, m = m_for([(50, 0.9), (40, 0.1), (60, 0.9)])
    assert m["longest_stretch_m"] == 60
    assert m["longest_stretch_segment_ids"] == ["A-2"]
    assert m["longest_stretch_bounds_m"] == [90.0, 150.0]


def test_no_concerning_segment_reports_empty():
    net, m = m_for([(50, 0.1), (60, 0.2)])
    assert m["longest_stretch_segment_ids"] == []
    assert m["longest_stretch_m"] == 0.0
    assert m["longest_stretch_bounds_m"] == [0.0, 0.0]
    assert m["longest_stretch_edge_index"] is None


def test_first_maximal_run_wins_on_tie():
    net, m = m_for([(50, 0.9), (40, 0.1), (50, 0.9)])
    assert m["longest_stretch_segment_ids"] == ["A-0"]
    assert m["longest_stretch_edge_index"] == [0, 0]


def test_longest_run_value_unchanged_and_plan_cards_carry_fields():
    segs, risks = counterexample()
    net = make_net(segs, risks)
    res = plan(net, "S", "T")
    for c in res["cards"]:
        assert longest_run(net, c["edges"]) == c["longest_stretch_m"]
        assert abs(ids_len(net, c["longest_stretch_segment_ids"]) - c["longest_stretch_m"]) < 1e-6
        a, b = c["longest_stretch_edge_index"]
        assert c["segment_ids"][a] == c["longest_stretch_segment_ids"][0]
        assert c["segment_ids"][b] == c["longest_stretch_segment_ids"][-1]


def test_api_card_payload_includes_fields():
    from fastapi.testclient import TestClient
    from app import main
    r = TestClient(main.app).post("/api/route", json={"start": [26.1871278, 91.6887413],
                                                       "end": [26.1870157, 91.6957447], "hour": 22}).json()
    for c in r["cards"]:
        for k in ("longest_stretch_segment_ids", "longest_stretch_bounds_m", "longest_stretch_edge_index"):
            assert k in c
        a, b = c["longest_stretch_edge_index"]
        ids = c["longest_stretch_segment_ids"]
        assert c["segment_ids"][a] == ids[0] and c["segment_ids"][b] == ids[-1]
        assert c["longest_stretch_bounds_m"][1] - c["longest_stretch_bounds_m"][0] >= c["longest_stretch_m"] - 1e-6
