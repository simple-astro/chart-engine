"""Every script on the main page is addressed by a fingerprint of its content, so a changed file is never served
from an old browser cache (a stale houses.js once broke "Generate chart")."""
import hashlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_each_script_has_its_content_fingerprint():
    r = TestClient(app).get("/")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    srcs = re.findall(r'<script src="/static/([\w.-]+\.js)(?:\?v=(\w+))?"', r.text)
    assert len(srcs) >= 10
    for name, v in srcs:
        assert v == hashlib.sha1((STATIC / name).read_bytes()).hexdigest()[:10], name
