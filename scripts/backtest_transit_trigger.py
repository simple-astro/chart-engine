"""Does a transit trigger pick the book's dated events better than chance?

Run: .venv/bin/python scripts/backtest_transit_trigger.py
Result (2026-10-09): the strict KP trigger fired near none of 15 events (base ~8% of days); the soft
"star or sub of a dasha lord" rule fired as often on random days as on event days (lift x1.0).
"""
import sys
from datetime import date, timedelta

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app import transit_view, transit_events as te  # noqa: E402
from test_book_backtest import EVENTS  # noqa: E402

cl = TestClient(app)
SPAN, WINS = 365, (0, 15, 30)


def soft(table, lords, topic):
    return [r for r in table if r["planet"] in te.SLOW and r["topics"][topic] == "supports"
            and (r["star_lord"] in lords or r["sub_lord"] in lords)]


VARIANTS = {
    "strict + retro rule": lambda t, l, k: te.strict_triggers(t, l, k, skip_inert=True),
    "strict, no retro rule": lambda t, l, k: te.strict_triggers(t, l, k, skip_inert=False),
    "soft (star or sub of a dasha lord)": soft,
}

res = {v: {"hit": {w: 0 for w in WINS}, "base": {w: [] for w in WINS}, "dba_hit": 0, "dba_base": [],
           "dba_hit15": 0, "dba_base15": []} for v in VARIANTS}
n = 0
for label, dob, tob, (lat, lon), topic, when, dba in EVENTS:
    if when is None:
        continue
    n += 1
    c = cl.post("/chart", json={"dob": dob, "tob": tob + ":00", "lat": lat, "lon": lon, "tz_name": "Asia/Kolkata"}).json()
    prof = {"chart": c, "request": {"tz_name": "Asia/Kolkata"}}
    E = date.fromisoformat(when)
    days = [E + timedelta(days=i) for i in range(-SPAN - 30, SPAN + 31)]
    fired = {v: {} for v in VARIANTS}
    lords_on = {}
    for d in days:
        ov = transit_view.overlay(prof, d)
        lords = {x["lord"] for x in ov["dasha"]}
        lords_on[d] = tuple(x["lord"] for x in ov["dasha"])
        table = te.rows(c, ov["planets"], [topic])
        for v, f in VARIANTS.items():
            fired[v][d] = bool(f(table, lords, topic))
    core = [E + timedelta(days=i) for i in range(-SPAN, SPAN + 1)]
    same = [d for d in core if lords_on[d] == lords_on[E]]  # days in the event's own D-B-A period
    for v in VARIANTS:
        F = fired[v]
        near = lambda d, w: any(F[d + timedelta(days=i)] for i in range(-w, w + 1))
        for w in WINS:
            res[v]["hit"][w] += near(E, w)
            res[v]["base"][w].append(sum(near(d, w) for d in core) / len(core))
        res[v]["dba_hit"] += F[E]
        res[v]["dba_base"].append(sum(F[d] for d in same) / len(same))
        res[v]["dba_hit15"] += near(E, 15)
        res[v]["dba_base15"].append(sum(near(d, 15) for d in same) / len(same))
    print(f"{label:24} {topic:14} DBA {'-'.join(lords_on[E])}: " +
          "  ".join(f"{v.split()[0]}={'Y' if fired[v][E] else '.'}" for v in VARIANTS), flush=True)

print(f"\n{n} dated events\n")
for v, r in res.items():
    print(f"== {v}")
    for w in WINS:
        base = sum(r["base"][w]) / n
        print(f"  within ±{w:>2} days: hit {r['hit'][w]}/{n} = {r['hit'][w]/n:.0%}   base {base:.0%}   "
              f"lift ×{(r['hit'][w]/n)/base:.2f}" if base else f"  ±{w}: base 0")
    b = sum(r["dba_base"]) / n
    b15 = sum(r["dba_base15"]) / n
    print(f"  inside the event's own DBA period: exact day hit {r['dba_hit']}/{n} vs base {b:.0%}"
          f"{f' (lift ×{(r['dba_hit']/n)/b:.2f})' if b else ''};  ±15d hit {r['dba_hit15']}/{n} vs base {b15:.0%}"
          f"{f' (lift ×{(r['dba_hit15']/n)/b15:.2f})' if b15 else ''}")
