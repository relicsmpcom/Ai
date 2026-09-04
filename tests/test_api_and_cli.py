import json

import pytest
from fastapi.testclient import TestClient

from wia.api import app
from wia.cli import main

client = TestClient(app)

LONG = (
    "In today's fast-paced digital landscape, organizations must leverage innovative solutions to "
    "optimize their workflows. Furthermore, it is important to note that a comprehensive framework "
    "plays a crucial role in driving sustainable growth. Additionally, businesses can streamline "
    "operations, enhance productivity, and empower stakeholders across the entire ecosystem."
)


def test_health_exposes_what_is_loaded():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["detector"]["features"] > 40
    assert body["detector"]["trained"] is True
    assert "disclaimer" in body


def test_detect_returns_a_distribution_and_a_disclaimer():
    body = client.post("/detect", json={"text": LONG}).json()
    assert abs(sum((body["human_probability"], body["mixed_probability"],
                    body["ai_probability"])) - 1.0) < 1e-6
    assert body["disclaimer"]
    assert body["language"] == "en"


def test_detect_rejects_empty_text():
    assert client.post("/detect", json={"text": "  "}).status_code == 400


def test_humanize_returns_candidates_with_meaning_evidence():
    body = client.post("/humanize", json={"text": LONG, "mode": "professional_english"}).json()
    assert body["candidates"]
    for candidate in body["candidates"]:
        assert "meaning" in candidate["scores"]
        assert "violations" in candidate["scores"]["meaning"]
    assert body["recommended"]


def test_humanize_honours_a_mode():
    body = client.post("/humanize", json={"text": LONG, "mode": "academisch_nederlands"}).json()
    assert body["options"]["formality"] == 6
    assert body["options"]["language"] == "nl"


def test_analyze_and_compare():
    analysis = client.post("/analyze", json={"text": LONG}).json()
    assert analysis["words"] > 40
    assert "issues" in analysis
    comparison = client.post("/compare", json={
        "original": "Revenue grew approximately 18% in Q3.",
        "rewrite": "Revenue grew about 18% in Q3.",
    }).json()
    assert comparison["meaning"]["passed"] is True


def test_meaning_check_endpoint_blocks_drift():
    body = client.post("/meaning-check", json={
        "original": "Revenue grew approximately 18% in Q3.",
        "rewrite": "Revenue grew more than 30% in Q3.",
    }).json()
    assert body["passed"] is False


def test_style_profile_warns_about_thin_samples():
    body = client.post("/style-profile", json={"samples": ["short sample of writing"]}).json()
    assert "sketch" in body["advice"]


def test_features_endpoint_publishes_the_measurements():
    body = client.get("/features").json()
    assert len(body["features"]) > 40
    assert all(f["description"] for f in body["features"])
    assert len(body["operations"]) > 20


def test_index_serves_the_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "WIA" in response.text


@pytest.mark.parametrize("argv", [
    ["detect", LONG, "--json"],
    ["humanize", LONG, "--json"],
    ["analyze", LONG, "--json"],
    ["features", "--json"],
    ["bench", "--summary"],
])
def test_cli_commands_emit_json(argv, capsys):
    assert main(argv) == 0
    out = capsys.readouterr().out
    json.loads(out)


def test_cli_compare(capsys):
    assert main(["compare", "Revenue grew 18% in Q3.", "Revenue rose 18% in Q3.", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["meaning"]["passed"] is True


def test_cli_style(capsys):
    assert main(["style", "ok so quick update, deploy went fine. i'll watch it tomorrow.",
                 "--json"]) == 0
    assert "formality" in json.loads(capsys.readouterr().out)
