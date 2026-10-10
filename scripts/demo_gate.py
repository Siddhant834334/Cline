import json
import random
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, db
from app.conditions import build_net, scenario_departure
from app.generate import generate, write_db, load_scenario
from app.graph import load_segments, components, node_coords
from app.route import plan, fastest

N_PAIRS = 40
MIN_MIN, MAX_MIN = 8.0, 15.0
DARK_M = 200.0
GAIN_M = 100.0
HOURS = (18, 20, 22, 1)
DEMO_HOUR = 22
PCT_LO, PCT_HI = 18.0, 28.0
SUBSET_BASELINE = 0.30
SAMPLE_SEED = 4242
OUT = ROOT / "data" / "demo_pairs.json"


def calmest_of(res):
    for c in res["cards"]:
        if c["name"] == "calmest":
            return c
    return None


def classify(res):
    fast = res["cards"][0]
    calm = calmest_of(res)
    if calm is None:
        return "collapsed", fast, None, 0.0
    gain = fast["longest_stretch_m"] - calm["longest_stretch_m"]
    return ("improved_100" if gain >= GAIN_M else "improved_lt100"), fast, calm, gain


def main():
    sc = load_scenario()
    segs = load_segments()
    tmp = Path(tempfile.mkdtemp()) / "gate.db"
    con = db.connect(tmp)
    write_db(con, segs, generate(segs, sc))

    print(f"scenario {sc['scenario_version']} seed={sc['seed']} zone_cells={sc['zone_cells']} noise={sc['noise']}")
    print(f"TAU={config.TAU} R={config.R_M} DELTA={config.DELTA_M} DETOUR={config.DETOUR_FACTOR}")
    print("\nhour  concerning%  median_risk  no_data")
    pct = {}
    for h in HOURS:
        net = build_net(con, segs, scenario_departure(sc["base_date"], h))
        pct[h] = 100.0 * sum(net.conc) / len(net.conc)
        print(f"{h:02d}    {pct[h]:6.1f}       {statistics.median(net.risk):.3f}        {net.status.count('no_data')}")

    net = build_net(con, segs, scenario_departure(sc["base_date"], DEMO_HOUR))
    big = components(segs)[0]
    rng = random.Random(SAMPLE_SEED)
    pairs, attempts = [], 0
    while len(pairs) < N_PAIRS and attempts < 20000:
        attempts += 1
        s, t = rng.sample(big, 2)
        f = fastest(net, s, t)
        if f and MIN_MIN * 60 <= f[2] <= MAX_MIN * 60:
            pairs.append((s, t))
    print(f"\nsampled {len(pairs)} OD pairs with fastest {MIN_MIN:g}-{MAX_MIN:g} min at hour {DEMO_HOUR} "
          f"({attempts} draws, sample seed {SAMPLE_SEED})")

    rows = []
    for s, t in pairs:
        res = plan(net, s, t)
        kind, fast, calm, gain = classify(res)
        rows.append({"s": s, "t": t, "kind": kind, "gain": gain, "fast": fast, "calm": calm})

    def counts(rs):
        return {k: sum(1 for r in rs if r["kind"] == k) for k in ("collapsed", "improved_lt100", "improved_100")}

    allc = counts(rows)
    sub = [r for r in rows if r["fast"]["longest_stretch_m"] >= DARK_M]
    subc = counts(sub)
    print(f"\nall pairs (n={len(rows)}): collapsed={allc['collapsed']} improved<{GAIN_M:g}m={allc['improved_lt100']} "
          f"improved>={GAIN_M:g}m={allc['improved_100']}")
    print(f"fastest longest stretch >= {DARK_M:g} m (n={len(sub)}): collapsed={subc['collapsed']} "
          f"improved<{GAIN_M:g}m={subc['improved_lt100']} improved>={GAIN_M:g}m={subc['improved_100']}")

    share = subc["improved_100"] / len(sub) if sub else 0.0
    ok_sub = bool(sub) and share >= SUBSET_BASELINE
    ok_pct = PCT_LO <= pct[DEMO_HOUR] <= PCT_HI
    print(f"\ncheck subset >=100m share {100 * share:.1f}% (recorded baseline, not a target: "
          f">= {100 * SUBSET_BASELINE:.0f}%): {'PASS' if ok_sub else 'FAIL'}")
    print(f"check hour-{DEMO_HOUR} concerning {pct[DEMO_HOUR]:.1f}% (need {PCT_LO:g}-{PCT_HI:g}%): {'PASS' if ok_pct else 'FAIL'}")

    coords = node_coords(segs)
    best = sorted([r for r in rows if r["kind"] == "improved_100"], key=lambda r: -r["gain"])[:5]
    out = []
    for n, r in enumerate(best, 1):
        out.append({
            "label": f"Demo pair {n}",
            "start": coords[r["s"]], "end": coords[r["t"]], "hour": DEMO_HOUR,
            "fastest_longest_stretch_m": round(r["fast"]["longest_stretch_m"], 1),
            "calmest_longest_stretch_m": round(r["calm"]["longest_stretch_m"], 1),
            "fastest_time_min": round(r["fast"]["time_s"] / 60, 1),
            "calmest_time_min": round(r["calm"]["time_s"] / 60, 1),
            "scenario_version": sc["scenario_version"], "scenario_seed": sc["seed"],
        })
    print("\nbest pairs:")
    for p in out:
        print(f"  {p['label']}: start {p['start']} end {p['end']} | fastest {p['fastest_time_min']} min / "
              f"{p['fastest_longest_stretch_m']} m | calmest {p['calmest_time_min']} min / {p['calmest_longest_stretch_m']} m")

    passed = ok_sub and ok_pct
    doc = {
        "gate_status": "pass" if passed else "fail",
        "scenario_version": sc["scenario_version"], "scenario_seed": sc["seed"], "sample_seed": SAMPLE_SEED,
        "concerning_pct_by_hour": {f"{h:02d}": round(pct[h], 1) for h in HOURS},
        "all_pairs": {"n": len(rows), **allc},
        "dark_subset": {"min_fastest_longest_stretch_m": DARK_M, "n": len(sub), **subc},
        "checks": {
            "dark_subset_improved_100_share_pct": round(100 * share, 1),
            "dark_subset_baseline_pct": round(100 * SUBSET_BASELINE),
            "dark_subset_ok": ok_sub,
            "hour22_concerning_band_pct": [PCT_LO, PCT_HI],
            "hour22_concerning_ok": ok_pct,
        },
        "pairs": out,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)} (gate_status={doc['gate_status']})")
    print("GATE", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
