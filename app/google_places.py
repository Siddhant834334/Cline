import json
import os
import urllib.request

URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.location,places.primaryType,places.primaryTypeDisplayName"
TIMEOUT_S = 8
ATTRIBUTION = "Place results from Google"


def api_key():
    return os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()


def enabled():
    return bool(api_key())


def build_request(q, limit, bbox):
    s, w, n, e = bbox
    body = {
        "textQuery": q,
        "pageSize": max(1, min(int(limit), 20)),
        "languageCode": "en",
        "locationRestriction": {"rectangle": {"low": {"latitude": s, "longitude": w},
                                              "high": {"latitude": n, "longitude": e}}},
    }
    return urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": api_key(), "X-Goog-FieldMask": FIELD_MASK})


def parse(data, in_bbox):
    out = []
    for p in data.get("places", []):
        loc = p.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        name = (p.get("displayName") or {}).get("text", "").strip()
        if lat is None or lon is None or not name or not in_bbox(lat, lon):
            continue
        kind = (p.get("primaryTypeDisplayName") or {}).get("text") or (p.get("primaryType") or "").replace("_", " ")
        out.append({"name": name, "label": f"{name} ({kind})" if kind else name, "kind": kind,
                    "lat": round(lat, 7), "lon": round(lon, 7), "source": "google",
                    "place_id": p.get("id"), "address": p.get("formattedAddress", "")})
    return out


def search(q, limit, bbox, in_bbox, opener=None):
    req = build_request(q, limit, bbox)
    with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT_S) as r:
        return parse(json.loads(r.read()), in_bbox)
