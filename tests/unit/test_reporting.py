"""Tests for the reporting utilities that generate PDFs from JSON artefacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

pytest.importorskip("reportlab")

from utils.reporting import convert_research_artifacts_to_pdfs


@pytest.fixture(
    params=["path", "mapping", "mixed"],
)
def artifact_inputs(tmp_path: Path, request) -> Tuple[object, object, Path]:
    dossier_data = {"company": "Acme", "summary": "Example"}
    similar_data = {"results": ["Acme Subsidiary"], "metadata": {"link": "https://example.com"}}

    dossier_path = tmp_path / "dossier.json"
    similar_path = tmp_path / "similar.json"
    dossier_path.write_text(json.dumps(dossier_data), encoding="utf-8")
    similar_path.write_text(json.dumps(similar_data), encoding="utf-8")

    if request.param == "path":
        dossier_source: object = dossier_path
        similar_source: object = similar_path
    elif request.param == "mapping":
        dossier_source = dossier_data
        similar_source = similar_data
    else:
        dossier_source = dossier_path
        similar_source = similar_data

    output_dir = tmp_path / f"pdfs_{request.param}"
    return dossier_source, similar_source, output_dir


def test_convert_research_artifacts_to_pdfs_creates_files(
    artifact_inputs: Tuple[object, object, Path]
) -> None:
    dossier_input, similar_input, output_dir = artifact_inputs

    result = convert_research_artifacts_to_pdfs(
        dossier_input,
        similar_input,
        output_dir=output_dir,
    )

    dossier_pdf = Path(result["dossier_pdf"])
    similar_pdf = Path(result["similar_companies_pdf"])

    assert dossier_pdf.exists()
    assert similar_pdf.exists()
    assert dossier_pdf.stat().st_size > 0
    assert similar_pdf.stat().st_size > 0
    assert dossier_pdf.parent == output_dir
    assert similar_pdf.parent == output_dir


def test_convert_research_artifacts_names_follow_inputs(tmp_path: Path) -> None:
    dossier_artifact = tmp_path / "custom_dossier_payload.json"
    similar_artifact = tmp_path / "candidate-list.json"
    dossier_artifact.write_text(json.dumps({"company": "Example"}), encoding="utf-8")
    similar_artifact.write_text(json.dumps({"results": []}), encoding="utf-8")

    result = convert_research_artifacts_to_pdfs(
        dossier_artifact,
        {"results": []},
        output_dir=tmp_path,
    )

    dossier_pdf = Path(result["dossier_pdf"])
    similar_pdf = Path(result["similar_companies_pdf"])

    assert dossier_pdf.name == "custom_dossier_payload.pdf"
    assert similar_pdf.name == "similar_companies.pdf"
