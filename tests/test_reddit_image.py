"""The chart image for Reddit (app/static/redditimg.js): what goes on the image and into the text post, worked out
from a real /chart response under node, and the Share image menu that opens it."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
NODE = shutil.which("node")
SUKH = {"name": "Sukh", "place": "Chandigarh, Chandigarh, India", "dob": "1987-09-01", "tob": "14:30:00", "lat": 30.73629,
        "lon": 76.7884, "tz_name": "Asia/Kolkata", "tob_unknown": False, "ayanamsha": "krishnamurti", "node_type": "mean"}


def _run(req: dict, now: str = "2026-10-23T12:00:00Z") -> dict:
    chart = TestClient(app).post("/chart", json=req).json()
    code = (f"globalThis.window=globalThis;const _N=Date.parse({json.dumps(now)});Date.now=()=>_N;"
            f"{(STATIC / 'redditimg.js').read_text()}\n"
            f"const T=window._redditImageForTest,F=T.facts({json.dumps(chart)},{json.dumps(req)},null);"
            "console.log(JSON.stringify({post:T.post(F),md:F.md.lord,ad:F.ad.lord,lords:F.keyLords,L9:F.L9,"
            "planets:F.planets.map(q=>[q.p,q.marks,q.dg,q.house,q.kar])}))")
    return json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_image_facts_for_sukh():
    r = _run(SUKH)
    p = {name: (marks, dg, house, kar) for name, marks, dg, house, kar in r["planets"]}
    assert p["Moon"][:3] == ("↓", "Debilitated", 12)  # the arrow on the chart means debilitated
    assert p["Jupiter"][0] == "ᴿ" and p["Jupiter"][2] == 5
    assert all("ᶜ" in p[x][0] for x in ("Mars", "Mercury", "Venus"))
    assert p["Mercury"][3] == "AK" and p["Saturn"][3] == "AmK"
    assert (r["md"], r["ad"]) == ("Venus", "Mercury")
    assert r["lords"][0] == ["Lagna", "Jupiter", 5] and ["Moon sign", "Mars", 9] in r["lords"]
    assert r["L9"] == 1  # Taurus navamsa lagna


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_post_for_reddit_has_tables_and_no_birth_details():
    post = _run(SUKH)["post"]
    assert post["title"].startswith("[Chart] Sagittarius lagna · Venus–Mercury dasha · ")
    body = post["body"]
    assert "| Planet | Sign | Degree | Nakshatra | House | Dignity |" in body
    assert "| Moon | Scorpio | 17°36′ | Jyeshtha 1 | 12 | Debilitated |" in body
    assert "| Mahadasha | Venus | Jun 2010 | Jun 2030 |" in body and "| Antardasha | Mercury |" in body
    assert "**D9 lagna:** Taurus · KP ayanamsa" in body and "simplejyotish.com" in body
    for private in ("Sukh", "1987", "14:30", "Chandigarh"):  # the post never carries birth details
        assert private not in body and private not in post["title"]


def test_share_image_menu_offers_the_reddit_image():
    html = (STATIC / "index.html").read_text()
    assert '<script src="/static/redditimg.js' in html
    assert "Chart for Reddit" in html and "window.redditImage(lastChart,lastReq,CHART_STYLE)" in html
