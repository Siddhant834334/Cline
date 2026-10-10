import glob
import json
import networkx as nx
from shapely.geometry import LineString
from . import config

EXCLUDE_HW = {"motorway", "motorway_link", "trunk", "trunk_link", "construction", "proposed",
              "abandoned", "platform", "raceway", "bus_guideway", "escape", "busway", "elevator"}
BLOCKED = {"no", "private"}
BBOX = (26.1795, 91.6830, 26.2010, 91.7060)


def walkable(tags):
    hw = tags.get("highway")
    if not hw or hw in EXCLUDE_HW or tags.get("area") == "yes":
        return False
    if tags.get("foot") in BLOCKED:
        return False
    if tags.get("access") == "no" and tags.get("foot") not in {"yes", "designated", "permissive"}:
        return False
    if tags.get("access") == "private" and not config.CAMPUS_MEMBER_ACCESS:
        return False
    return True


def load_tiles(pattern):
    nodes, ways = {}, {}
    for p in sorted(glob.glob(pattern)):
        for el in json.load(open(p))["elements"]:
            if el["type"] == "node":
                nodes[el["id"]] = el
            elif el["type"] == "way":
                ways[el["id"]] = el
    return nodes, ways


def build_graph(nodes, ways):
    import pyproj
    crs = "EPSG:32646"
    tf = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    use = {wid: w for wid, w in ways.items() if walkable(w.get("tags", {}))}
    count = {}
    for w in use.values():
        for i, n in enumerate(w["nodes"]):
            count[n] = count.get(n, 0) + (2 if i in (0, len(w["nodes"]) - 1) else 1)
    barrier_nodes = {nid for nid, n in nodes.items() if n.get("tags", {}).get("foot") == "no" or n.get("tags", {}).get("access") == "no" or (n.get("tags", {}).get("access") == "private" and not config.CAMPUS_MEMBER_ACCESS)}
    G = nx.MultiGraph(crs=crs)
    xy = {}
    for nid, n in nodes.items():
        if nid in count:
            xy[nid] = tf.transform(n["lon"], n["lat"])
    for wid, w in sorted(use.items()):
        ns = [n for n in w["nodes"] if n in xy]
        if len(ns) < 2:
            continue
        start = 0
        for i in range(1, len(ns)):
            if i == len(ns) - 1 or count.get(ns[i], 0) > 1 or ns[i] in barrier_nodes:
                part = ns[start:i + 1]
                if len(set(part)) >= 2:
                    u, v = part[0], part[-1]
                    for nid in (u, v):
                        G.add_node(nid, x=xy[nid][0], y=xy[nid][1], lon=nodes[nid]["lon"], lat=nodes[nid]["lat"])
                    geom = LineString([xy[n] for n in part])
                    G.add_edge(u, v, osmid=str(wid), access_profile="campus_member" if w["tags"].get("access") == "private" else "public", highway=w["tags"].get("highway"),
                               access=w["tags"].get("access", "yes"), foot=w["tags"].get("foot", ""),
                               length=geom.length, geometry=geom.wkt)
                start = i
    for b in barrier_nodes & set(G.nodes):
        G.remove_node(b)
    return G


def save_graphml(G, path=config.GRAPHML):
    nx.write_graphml(G, path)


def to_segments(G):
    import pyproj
    from shapely import wkt
    from .graph import split_edge
    to_wgs = pyproj.Transformer.from_crs(G.graph["crs"], "EPSG:4326", always_xy=True)
    segs = []
    for u, v, k, d in sorted(G.edges(keys=True, data=True), key=lambda x: (str(x[0]), str(x[1]), x[2])):
        geom = wkt.loads(d["geometry"])
        if geom.length < 0.01:
            continue
        segs.extend(split_edge(str(u), str(v), k, d["osmid"], geom, config.SPLIT_M, G.graph["crs"], to_wgs,
                               d.get("access_profile", "public")))
    return segs


def main():
    from .graph import save_segments, components
    nodes, ways = load_tiles(str(config.DATA / "osm_tiles" / "t*.json"))
    G = build_graph(nodes, ways)
    save_graphml(G)
    segs = to_segments(G)
    save_segments(segs)
    comps = components(segs)
    print(f"ways_walkable={sum(1 for w in ways.values() if walkable(w.get('tags', {})))} graph_nodes={G.number_of_nodes()} graph_edges={G.number_of_edges()}")
    print(f"segments={len(segs)} seg_nodes={sum(map(len, comps))} components={len(comps)} largest={len(comps[0])}")


if __name__ == "__main__":
    main()
