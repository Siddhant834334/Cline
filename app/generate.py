import json
import random
import hashlib
from datetime import datetime, timedelta
from . import config, db
from .catalog import CATALOG, check_catalog

FIELDS = list(config.FIELD_DIRECTION)
HOURS = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5]
LATE = {18: 0.0, 19: 0.1, 20: 0.2, 21: 0.35, 22: 0.5, 23: 0.7}

DEFAULT_SCENARIO = {
    "scenario_version": "v1",
    "seed": 20251010,
    "base_date": "2025-10-10",
    "zones": {
        "academic": {
            "lighting_level": 0.85,
            "activity_level": 0.6,
            "walkability": 0.8,
            "sightline_depth": 0.7,
            "open_poi_distance": 0.3,
            "dog_report_risk": 0.2,
            "waterlogging": 0.1
        },
        "hostel": {
            "lighting_level": 0.8,
            "activity_level": 0.8,
            "walkability": 0.7,
            "sightline_depth": 0.6,
            "open_poi_distance": 0.2,
            "dog_report_risk": 0.3,
            "waterlogging": 0.1
        },
        "residential": {
            "lighting_level": 0.75,
            "activity_level": 0.62,
            "walkability": 0.6,
            "sightline_depth": 0.58,
            "open_poi_distance": 0.5,
            "dog_report_risk": 0.4,
            "waterlogging": 0.2
        },
        "periphery": {
            "lighting_level": 0.45,
            "activity_level": 0.3,
            "walkability": 0.4,
            "sightline_depth": 0.3,
            "open_poi_distance": 0.8,
            "dog_report_risk": 0.6,
            "waterlogging": 0.35
        },
        "lakeside": {
            "lighting_level": 0.5,
            "activity_level": 0.4,
            "walkability": 0.5,
            "sightline_depth": 0.4,
            "open_poi_distance": 0.7,
            "dog_report_risk": 0.5,
            "waterlogging": 0.5
        }
    },
    "zone_cells": 10,
    "noise": 0.08,
    "late_night_decay": {
        "lighting_level": 0.05,
        "activity_level": 0.35,
        "open_poi_distance": -0.4
    },
    "missing_field_rate": 0.08,
    "all_missing_rate": 0.02,
    "stale_rate": 0.1,
    "stale_hours": [
        14,
        30
    ],
    "contradictory_report_rate": 0.01,
    "zone_weights": {
        "academic": 0.28,
        "hostel": 0.24,
        "residential": 0.22,
        "periphery": 0.16,
        "lakeside": 0.1
    }
}


def _zone(seg, sc, bounds):
    la, lo = seg["lonlat"][len(seg["lonlat"]) // 2]
    s, w, n, e = bounds
    k = sc["zone_cells"]
    i = min(k - 1, int((la - s) / max(1e-12, n - s) * k))
    j = min(k - 1, int((lo - w) / max(1e-12, e - w) * k))
    return zone_for_cell(sc, i, j)


def zone_for_cell(sc, i, j):
    h = hashlib.sha256(f"{sc['seed']}:{i}:{j}".encode()).digest()
    u = int.from_bytes(h[:8], "big") / 2 ** 64
    weights = sc["zone_weights"]
    total = sum(weights.values())
    acc = 0.0
    for name, wgt in weights.items():
        acc += wgt / total
        if u < acc:
            return name
    return list(weights)[-1]


def slot_time(base, hour):
    day = base if hour >= 18 else base + timedelta(days=1)
    return day.replace(hour=hour)


def generate(segments, sc):
    rng = random.Random(sc["seed"])
    lats = [p[0] for s in segments for p in s["lonlat"]]
    lons = [p[1] for s in segments for p in s["lonlat"]]
    bounds = (min(lats), min(lons), max(lats), max(lons))
    base = datetime.fromisoformat(sc["base_date"] + "T18:00:00")
    ver = sc["scenario_version"]
    rows = []
    for seg in segments:
        sid = seg["segment_id"]
        z = sc["zones"][_zone(seg, sc, bounds)]
        bias = {f: rng.gauss(0, sc["noise"]) for f in FIELDS}
        if rng.random() < sc["all_missing_rate"]:
            missing = set(FIELDS)
        else:
            missing = {f for f in FIELDS if rng.random() < sc["missing_field_rate"]}
        stale_h = rng.uniform(*sc["stale_hours"]) if rng.random() < sc["stale_rate"] else rng.uniform(0, 2)
        contra = len(missing) < len(FIELDS) and rng.random() < sc["contradictory_report_rate"]
        contra_v = round(rng.uniform(0, 0.2), 4)
        for hour in HOURS:
            slot = slot_time(base, hour)
            at = slot - timedelta(hours=stale_h)
            for f in FIELDS:
                if f in missing:
                    continue
                v = z[f] + bias[f] - sc["late_night_decay"].get(f, 0.0) * LATE.get(hour, 1.0)
                rows.append((sid, f, round(min(1.0, max(0.0, v)), 4), hour, "synthetic_generator",
                             at.isoformat(timespec="seconds"),
                             (at + timedelta(hours=48)).isoformat(timespec="seconds"), "n/a", ver))
            if contra:
                rows.append((sid, "lighting_level", contra_v, hour, "community_report",
                             slot.isoformat(timespec="seconds"),
                             (slot + timedelta(hours=24)).isoformat(timespec="seconds"), "unverified", ver))
    return rows


def write_db(con, segments, rows):
    for t in ("segment", "observation", "collection_catalog", "condition_event", "report"):
        con.execute(f"DELETE FROM {t}")
    con.executemany("INSERT INTO segment VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(s["segment_id"], s["u"], s["v"], s["edge_key"], s["parent_way_id"], s["length_m"],
                      s["walk_time_s"], s["pedestrian_access"], s["geometry_wkt"], s["crs"]) for s in segments])
    con.executemany("INSERT INTO observation(segment_id,field,value,hour_of_day,source,observed_at,valid_until,review_status,scenario_version) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO collection_catalog VALUES (?,?,?,?,?,?)", CATALOG)
    con.commit()
    check_catalog(con)


def rows_digest(rows):
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def load_scenario(path=config.SCENARIO):
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_SCENARIO, indent=2))
    return json.loads(path.read_text())


def main():
    from .graph import load_segments
    segments = load_segments()
    sc = load_scenario()
    rows = generate(segments, sc)
    con = db.connect()
    write_db(con, segments, rows)
    n_missing = con.execute("SELECT COUNT(*) FROM segment WHERE segment_id NOT IN (SELECT DISTINCT segment_id FROM observation WHERE source='synthetic_generator')").fetchone()[0]
    print(f"segments={len(segments)} observations={len(rows)} all_missing_segments={n_missing} digest={rows_digest(rows)[:16]}")


if __name__ == "__main__":
    main()
