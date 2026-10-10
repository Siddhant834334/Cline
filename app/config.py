import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = Path(os.environ.get("FNN_DB", DATA / "fnn.db"))
GRAPHML = DATA / "iitg.graphml"
SEGMENTS_JSON = DATA / "segments.json"
SCENARIO = DATA / "scenario_v1.json"

TAU = 0.5
R_M = 40.0
DELTA_M = 10.0
DETOUR_FACTOR = 1.4
WALK_SPEED_MPS = 1.25
SPLIT_M = 30.0
DEDUP_SHARE = 0.85
CAMPUS_MEMBER_ACCESS = True

FIELD_DIRECTION = {
    "lighting_level": -1, "activity_level": -1, "walkability": -1,
    "sightline_depth": -1, "open_poi_distance": +1,
    "dog_report_risk": +1, "waterlogging": +1,
}
WEIGHTS = {
    "lighting_level": 0.30, "activity_level": 0.20, "walkability": 0.10,
    "sightline_depth": 0.15, "open_poi_distance": 0.10,
    "dog_report_risk": 0.10, "waterlogging": 0.05,
}
UNKNOWN_DEFAULT = 0.70
STALE_AFTER_H = 12.0
MAX_STALE_ADD = 0.15

REVIEWER_TOKEN = os.environ.get("FNN_REVIEWER_TOKEN", "demo-reviewer-token")
SESSION_REPORT_CAP = 20

assert all(w >= 0 for w in WEIGHTS.values())
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
assert set(WEIGHTS) == set(FIELD_DIRECTION)
