import glob
import json
import threading
import time
import urllib.parse
import urllib.request
from . import config, google_places

BBOX = (26.1795, 91.6830, 26.2010, 91.7060)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "fear-free-night-navigator/0.1 (hackathon demo; github.com/shivanshi-tyagi30/Cline)"
MIN_INTERVAL_S = 1.1
TIMEOUT_S = 8
CACHE_MAX = 500
SKIP_KEYS = ("route", "railway", "public_transport")

_lock = threading.Lock()
_last_call = [0.0]
_cache = {}
_local = None


def in_bbox(lat, lon):
    s, w, n, e = BBOX
    return s <= lat <= n and w <= lon <= e


def _label(name, kind):
    return f"{name} ({kind})" if kind else name


def _kind(tags):
    for k in ("amenity", "building", "leisure", "tourism", "shop", "office", "natural", "landuse", "highway"):
        if k in tags and tags[k] not in ("yes",):
            return tags[k].replace("_", " ")
    return ""


def local_places():
    global _local
    if _local is not None:
        return _local
    nodes, items, seen = {}, [], set()
    tiles = sorted(glob.glob(str(config.DATA / "osm_tiles" / "t*.json")))
    elements = [el for p in tiles for el in json.load(open(p))["elements"]]
    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el["lat"], el["lon"])
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or el["type"] == "relation" or any(k in tags for k in SKIP_KEYS):
            continue
        if el["type"] == "node":
            lat, lon = el["lat"], el["lon"]
        else:
            pts = [nodes[n] for n in el.get("nodes", []) if n in nodes]
            if not pts:
                continue
            lat, lon = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        if not in_bbox(lat, lon):
            continue
        key = (name.lower(), round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        kind = _kind(tags)
        items.append({"name": name, "label": _label(name, kind), "kind": kind, "lat": round(lat, 7),
                      "lon": round(lon, 7), "source": "osm_tiles", "osm_id": f"{el['type']}/{el['id']}"})
    _local = sorted(items, key=lambda x: x["name"].lower())
    return _local


def search_local(q, limit):
    ql = q.lower().strip()
    hits = [p for p in local_places() if ql in p["name"].lower()]
    hits.sort(key=lambda p: (not p["name"].lower().startswith(ql), p["name"].lower()))
    return hits[:limit]


def _fetch(q, limit):
    s, w, n, e = BBOX
    params = {"q": q, "format": "jsonv2", "limit": str(limit), "viewbox": f"{w},{n},{e},{s}", "bounded": "1",
              "addressdetails": "0"}
    req = urllib.request.Request(NOMINATIM_URL + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                data = json.loads(r.read())
        finally:
            _last_call[0] = time.monotonic()
    out = []
    for r in data:
        lat, lon = float(r["lat"]), float(r["lon"])
        if not in_bbox(lat, lon):
            continue
        kind = (r.get("type") or "").replace("_", " ")
        street = r.get("display_name", "").split(",")[0].strip()
        name = r.get("name") or (f"Unnamed {kind} near {street}" if street else f"Unnamed {kind}")
        out.append({"name": name, "label": _label(name, kind), "kind": kind, "lat": round(lat, 7),
                    "lon": round(lon, 7), "source": "nominatim", "osm_id": f"{r.get('osm_type')}/{r.get('osm_id')}",
                    "display_name": r.get("display_name", "")})
    return out


ATTRIBUTION = {
    "google": google_places.ATTRIBUTION,
    "nominatim": "Data (c) OpenStreetMap contributors, ODbL. Search by Nominatim.",
    "osm_tiles": "Data (c) OpenStreetMap contributors, ODbL.",
    "none": "",
}


def _google(q, limit):
    return google_places.search(q, limit, BBOX, in_bbox)


def search(q, limit=8, fetch=None, google=None, google_on=None):
    q = " ".join((q or "").split())[:100]
    limit = max(1, min(int(limit), 20))
    if len(q) < 2:
        return {"query": q, "results": [], "source": "none", "note": "type at least 2 characters"}
    key = (q.lower(), limit)
    if key in _cache:
        return _cache[key]
    notes = []
    use_google = google_places.enabled() if google_on is None else google_on
    res = None
    if use_google:
        try:
            hits = (google or _google)(q, limit)
            if hits:
                res = {"query": q, "results": hits, "source": "google"}
            else:
                notes.append("google returned no campus results")
        except Exception as e:
            notes.append(f"google unavailable ({type(e).__name__})")
    if res is None:
        try:
            hits = (fetch or _fetch)(q, limit)
            res = {"query": q, "results": hits, "source": "nominatim"}
            if not hits:
                local = search_local(q, limit)
                if local:
                    res = {"query": q, "results": local, "source": "osm_tiles"}
        except Exception as e:
            notes.append(f"nominatim unavailable ({type(e).__name__})")
            res = {"query": q, "results": search_local(q, limit), "source": "osm_tiles"}
    if notes:
        res["note"] = "; ".join(notes)
    res["attribution"] = ATTRIBUTION[res["source"]]
    transient = any("unavailable" in n for n in notes)
    if not transient:
        if len(_cache) >= CACHE_MAX:
            _cache.clear()
        _cache[key] = res
    return res
