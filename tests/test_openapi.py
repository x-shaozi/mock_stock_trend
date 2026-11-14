from pathlib import Path

import yaml

from app.main import app


def test_openapi_document_matches_application() -> None:
    contract = Path(__file__).resolve().parents[1] / "docs" / "openapi.yaml"
    documented = yaml.safe_load(contract.read_text(encoding="utf-8"))

    assert documented == app.openapi()
