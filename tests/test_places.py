from fastapi.testclient import TestClient
from app import places


def fake(results):
    return lambda q, limit: results


import pytest


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    places._cache.clear()
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)


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
    assert "OpenStreetMap" in r["attribution"]
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


G_HIT = [{"name": "Central Library", "label": "Central Library (Library)", "kind": "Library",
          "lat": 26.1893, "lon": 91.6930, "source": "google", "place_id": "abc", "address": "IIT Guwahati"}]
NOM_HIT = [{"name": "N", "label": "N", "kind": "", "lat": 26.19, "lon": 91.69, "source": "nominatim", "osm_id": "n/1"}]


def test_google_used_first_when_enabled():
    r = places.search("library", google_on=True, google=lambda q, l: G_HIT, fetch=lambda q, l: NOM_HIT)
    assert r["source"] == "google" and r["results"][0]["name"] == "Central Library"
    assert r["attribution"] == "Place results from Google"


def test_google_skipped_without_key():
    def never(q, l):
        raise AssertionError("google must not be called without a key")
    r = places.search("library", google=never, fetch=lambda q, l: NOM_HIT)
    assert r["source"] == "nominatim"


def test_google_error_falls_back_to_nominatim_and_is_not_cached():
    def boom(q, l):
        raise OSError("403")
    r = places.search("library", google_on=True, google=boom, fetch=lambda q, l: NOM_HIT)
    assert r["source"] == "nominatim" and "google unavailable" in r["note"]
    assert ("library", 8) not in places._cache


def test_google_empty_falls_back():
    r = places.search("zzz place", google_on=True, google=lambda q, l: [], fetch=lambda q, l: NOM_HIT)
    assert r["source"] == "nominatim" and "no campus results" in r["note"]


def test_google_parse_restricts_to_campus_and_keeps_name_with_coords():
    from app import google_places
    data = {"places": [
        {"id": "p1", "displayName": {"text": "Lecture Hall Complex"}, "location": {"latitude": 26.1890, "longitude": 91.6915},
         "primaryTypeDisplayName": {"text": "University"}, "formattedAddress": "IITG"},
        {"id": "p2", "displayName": {"text": "Fancy Bazar"}, "location": {"latitude": 26.18, "longitude": 91.74}},
        {"id": "p3", "displayName": {"text": ""}, "location": {"latitude": 26.19, "longitude": 91.69}},
    ]}
    out = google_places.parse(data, places.in_bbox)
    assert [p["name"] for p in out] == ["Lecture Hall Complex"]
    assert out[0]["lat"] == 26.189 and out[0]["place_id"] == "p1" and out[0]["kind"] == "University"


def test_google_request_sends_key_in_header_and_campus_rectangle(monkeypatch):
    import json
    from app import google_places
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "k-123")
    req = google_places.build_request("canteen", 50, places.BBOX)
    body = json.loads(req.data)
    assert req.get_header("X-goog-api-key") == "k-123" and "k-123" not in req.full_url
    assert body["pageSize"] == 20
    rect = body["locationRestriction"]["rectangle"]
    assert rect["low"] == {"latitude": 26.1795, "longitude": 91.6830}
    assert rect["high"] == {"latitude": 26.2010, "longitude": 91.7060}
    assert "places.location" in req.get_header("X-goog-fieldmask")
