"""The service layer and the serverless build.

The browser build's whole premise is that the engine needs nothing but the
standard library, and that the HTTP API is a thin wrapper rather than a second
implementation. Both are load-bearing, so both are tested.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from wia import service

ROOT = Path(__file__).resolve().parent.parent

LONG = (
    "In today's fast-paced digital landscape, organizations must leverage innovative solutions to "
    "optimize their workflows. Furthermore, it is important to note that a comprehensive framework "
    "plays a crucial role in driving sustainable growth. Additionally, businesses can streamline "
    "operations, enhance productivity, and empower stakeholders across the entire ecosystem."
)


def test_every_route_is_reachable_through_handle():
    assert set(service.ROUTES) == {
        "/health", "/detect", "/humanize", "/analyze", "/compare",
        "/meaning-check", "/style-profile", "/modes", "/features",
    }
    assert service.handle("/health")["status"] == "ok"
    assert service.handle("modes")["modes"]  # leading slash is optional


def test_unknown_route_is_a_404_not_a_crash():
    with pytest.raises(service.ServiceError) as excinfo:
        service.handle("/nope")
    assert excinfo.value.status == 404


@pytest.mark.parametrize("path,payload", [
    ("/detect", {"text": "   "}),
    ("/analyze", {"text": ""}),
    ("/compare", {"original": "something", "rewrite": ""}),
    ("/style-profile", {"samples": []}),
])
def test_missing_input_is_a_clean_error(path, payload):
    with pytest.raises(service.ServiceError) as excinfo:
        service.handle(path, payload)
    assert excinfo.value.status == 400


def test_detect_and_humanize_work_without_any_web_framework():
    detected = service.handle("/detect", {"text": LONG})
    assert 0.0 <= detected["ai_probability"] <= 1.0
    assert detected["disclaimer"]

    rewritten = service.handle("/humanize", {"text": LONG, "mode": "natural_english"})
    assert rewritten["candidates"]
    assert rewritten["recommended"]


def test_the_api_layer_adds_no_second_implementation():
    # Pure source inspection — deliberately does not import FastAPI, so it
    # still guards the contract on a minimal install.
    """Every FastAPI route body should delegate, not compute.

    If someone re-implements an endpoint in the API layer, the browser build
    silently stops matching the server. Cheap structural check: no route
    function in app.py may do anything but call the service.
    """
    tree = ast.parse((ROOT / "wia" / "api" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in {"_call", "index"}:
            continue
        calls = {
            n.func.id for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "_call" in calls, f"{node.name} does not delegate to the service layer"


# ---------------------------------------------------------------- the build --
def test_the_engine_stays_standard_library_only():
    """The static build works only while this holds."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_browser_safe.py")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_static_build_produces_a_runnable_site(tmp_path):
    out = tmp_path / "site"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_pages.py"), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    assert (out / "index.html").exists()
    assert (out / "boot.js").exists()
    assert (out / ".nojekyll").exists()

    html = (out / "index.html").read_text(encoding="utf-8")
    assert '<script src="boot.js"></script>' in html

    with zipfile.ZipFile(out / "wia-package.zip") as zf:
        names = set(zf.namelist())
    # The engine and its data must be in the bundle...
    assert "wia/service.py" in names
    assert "wia/detector/weights.json" in names
    assert "wia/lexicons/nl.json" in names
    assert any(n.startswith("wia/data/humanbench/") for n in names)
    # ...and the web framework layer must not be.
    assert not any(n.startswith("wia/api/") for n in names)
    assert not any(n.endswith(".pyc") for n in names)
