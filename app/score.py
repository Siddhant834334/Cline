from datetime import datetime
from . import config


def oriented(field, value):
    v = min(1.0, max(0.0, float(value)))
    return 1.0 - v if config.FIELD_DIRECTION[field] < 0 else v


def segment_risk(obs, weights=None, now=None):
    weights = weights or config.WEIGHTS
    assert all(w >= 0 for w in weights.values())
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    observed = {k: obs[k] for k in weights if obs.get(k) is not None}
    coverage = len(observed) / len(weights)
    if not observed:
        return 1.0, 0.0, "no_data"
    risk = 0.0
    for k, w in weights.items():
        risk += w * (oriented(k, observed[k]) if k in observed else config.UNKNOWN_DEFAULT)
    stale_add = 0.0
    obs_at = obs.get("_observed_at")
    if obs_at is not None and now is not None:
        age_h = max(0.0, (now - obs_at).total_seconds() / 3600.0)
        stale_add = config.MAX_STALE_ADD * min(1.0, max(0.0, age_h - config.STALE_AFTER_H) / config.STALE_AFTER_H)
    return min(1.0, max(0.0, risk + stale_add)), coverage, "ok"


def parse_ts(s):
    return datetime.fromisoformat(s) if s else None
