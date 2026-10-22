"""Every non-Python file the app reads at runtime must be in the package data, or the server image lacks it
(the public homepage once returned 500 because app/home.html was not packaged)."""
from fnmatch import fnmatch
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_app_files_are_packaged():
    patterns = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["setuptools"]["package-data"]["app"]
    files = [p.relative_to(ROOT / "app").as_posix() for p in (ROOT / "app").rglob("*")
             if p.is_file() and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts]
    missing = [f for f in files if not any(fnmatch(f, pat) for pat in patterns)]
    assert not missing, f"add these to [tool.setuptools.package-data] in pyproject.toml: {missing}"
