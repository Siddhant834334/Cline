import os
import json
import math
from collections import defaultdict
from shapely.geometry import LineString
from shapely.ops import substring
from . import config

IITG_BBOX = dict(north=26.2010, south=26.1795, east=91.7060, west=91.6830)
BLOCKED_ACCESS = {"no", "private"}


def download_graph():
    import osmnx as ox
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(config.DATA / "osm_cache")
    ox.settings.overpass_rate_limit = False
    ox.settings.overpass_endpoint = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api")
    ox.settings.timeout = 240
    ox.settings.default_user_agent = "fear-free-night-navigator/0.1"
    G = ox.graph_from_bbox(bbox=(IITG_BBOX["north"], IITG_BBOX["south"], IITG_BBOX["east"], IITG_BBOX["west"]),
                           network_type="walk", simplify=True, retain_all=True)
    Gp = ox.project_graph(G)
    ox.save_graphml(Gp, config.GRAPHML)
    return Gp


def load_graph():
    import osmnx as ox
    return ox.load_graphml(config.GRAPHML)


def _access(data):
    for tag in ("access", "foot"):
        v = data.get(tag)
        if isinstance(v, list):
            v = v[0]
        if v in BLOCKED_ACCESS:
            return v
    return "yes"


def build_segments(Gp, split_m=config.SPLIT_M):
    import pyproj
    crs = str(Gp.graph["crs"])
    to_wgs = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    seen = set()
    segments = []
    for u, v, k, d in Gp.edges(keys=True, data=True):
        key = (min(u, v), max(u, v), k)
        if key in seen:
            continue
        seen.add(key)
        access = _access(d)
        if access in BLOCKED_ACCESS:
            continue
        geom = d.get("geometry")
        if geom is None:
            geom = LineString([(Gp.nodes[u]["x"], Gp.nodes[u]["y"]), (Gp.nodes[v]["x"], Gp.nodes[v]["y"])])
        way = d.get("osmid")
        way = str(way[0] if isinstance(way, list) else way)
        segments.extend(split_edge(str(u), str(v), k, way, geom, split_m, crs, to_wgs, access))
    return segments


def split_edge(u, v, k, way, geom, split_m, crs, to_wgs, access="yes"):
    total = geom.length
    n = max(1, math.ceil(total / split_m - 1e-9))
    out = []
    prev = u
    for i in range(n):
        a, b = total * i / n, total * (i + 1) / n
        piece = substring(geom, a, b)
        if piece.geom_type != "LineString":
            piece = LineString([piece.coords[0], piece.coords[0]])
        nxt = v if i == n - 1 else f"{u}_{v}_{k}_{i + 1}"
        length = b - a
        lonlat = [list(to_wgs.transform(x, y)) for x, y in piece.coords] if to_wgs else [list(c) for c in piece.coords]
        out.append({
            "segment_id": f"{u}-{v}-{k}-{i}", "u": prev, "v": nxt, "edge_key": k,
            "parent_way_id": way, "length_m": length,
            "walk_time_s": length / config.WALK_SPEED_MPS,
            "pedestrian_access": access, "geometry_wkt": piece.wkt, "crs": crs,
            "lonlat": [[round(c[1], 7), round(c[0], 7)] for c in lonlat],
        })
        prev = nxt
    return out


def adjacency(segments, closed=frozenset()):
    adj = defaultdict(list)
    for idx, s in enumerate(segments):
        if s["segment_id"] in closed:
            continue
        adj[s["u"]].append((s["v"], idx))
        adj[s["v"]].append((s["u"], idx))
    return adj


def components(segments):
    adj = adjacency(segments)
    seen, comps = set(), []
    for n in adj:
        if n in seen:
            continue
        stack, comp = [n], []
        seen.add(n)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y, _ in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        comps.append(comp)
    return sorted(comps, key=len, reverse=True)


def save_segments(segments, path=config.SEGMENTS_JSON):
    with open(path, "w") as f:
        json.dump(segments, f, separators=(",", ":"))


def load_segments(path=config.SEGMENTS_JSON):
    with open(path) as f:
        return json.load(f)


def node_coords(segments):
    c = {}
    for s in segments:
        c.setdefault(s["u"], s["lonlat"][0])
        c.setdefault(s["v"], s["lonlat"][-1])
    return c


def nearest_node(segments, lat, lon, allowed=None):
    best, bd = None, float("inf")
    for n, (la, lo) in node_coords(segments).items():
        if allowed is not None and n not in allowed:
            continue
        d = (la - lat) ** 2 + ((lo - lon) * math.cos(math.radians(lat))) ** 2
        if d < bd:
            best, bd = n, d
    return best


if __name__ == "__main__":
    Gp = download_graph() if not config.GRAPHML.exists() else load_graph()
    segs = build_segments(Gp)
    save_segments(segs)
    comps = components(segs)
    print(f"crs={Gp.graph['crs']} osm_nodes={Gp.number_of_nodes()} osm_edges={Gp.number_of_edges()}")
    print(f"segments={len(segs)} graph_nodes={sum(map(len, comps))} components={len(comps)} largest={len(comps[0])}")
