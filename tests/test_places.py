from fastapi.testclient import TestClient
from app import places


def fake(results):
    return lambda q, limit: results


def setup_function():
    places._cache.clear()


def test_local_places_inside_bbox_and_named():
    items = places.local_places()
    assert items
    assert all(p["name"] and places.in_bbox(p["lat"], p["lon"]) for p in items)
    assert not any("Rajdhani" in p["name"] for p in items)


def test_live_results_used_and_name_matches_coordinates():
    r = places.search("hostel", fetch=fake([{"name": "Gaurang Hostel", "lat": 26.19136, "lon": 91.70080,
                                              "label": "Gaurang Hostel (hostel)", "kind": "hostel",
                                              "source": "nominatim", "osm_id": "node/1"}]))
    assert r["source"] == "nominatim" and r["results"][0]["name"] == "Gaurang Hostel"
    assert r["results"][0]["lat"] == 26.19136


def test_network_failure_falls_back_to_offline_names():
    def boom(q, limit):
        raise OSError("offline")
    name = places.local_places()[0]["name"]
    r = places.search(name[:5], fetch=boom)
    assert r["source"] == "osm_tiles" and "unavailable" in r["note"]
    assert any(name[:5].lower() in p["name"].lower() for p in r["results"])


def test_short_query_rejected_without_network_call():
    def boom(q, limit):
        raise AssertionError("should not be called")
    assert places.search("a", fetch=boom)["results"] == []


def test_results_cached():
    calls = []
    def f(q, limit):
        calls.append(q)
        return []
    places.search("zzqq", fetch=f)
    places.search("zzqq", fetch=f)
    assert len(calls) == 1


def test_endpoint_adds_snapped_point(monkeypatch):
    from app import main
    monkeypatch.setattr(places, "_fetch", fake([{"name": "Academic Complex", "lat": 26.1862036, "lon": 91.6914258,
                                                 "label": "Academic Complex", "kind": "university",
                                                 "source": "nominatim", "osm_id": "way/1"}]))
    r = TestClient(main.app).get("/api/places/search", params={"q": "academic"}).json()
    p = r["results"][0]
    assert p["name"] == "Academic Complex" and "snapped" in p and p["snapped"]["distance_m"] < 500
    assert "OpenStreetMap" in r["attribution"]


def test_unnamed_place_is_labelled_not_given_street_name(monkeypatch):
    import io, json
    payload = [{"name": "", "display_name": "Footpath surrounding sports area, North Guwahati", "type": "library",
                "lat": "26.1893168", "lon": "91.6929809", "osm_type": "node", "osm_id": 5}]
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(places.urllib.request, "urlopen", lambda req, timeout: R(json.dumps(payload).encode()))
    monkeypatch.setattr(places, "MIN_INTERVAL_S", 0)
    out = places._fetch("library", 5)
    assert out[0]["name"] == "Unnamed library near Footpath surrounding sports area"
