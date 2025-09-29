"""Tests for the reporting utilities that generate PDFs from JSON artefacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

from utils.reporting import convert_research_artifacts_to_pdfs


def test_convert_research_artifacts_to_pdfs_creates_files(tmp_path: Path) -> None:
    dossier_data = {"company": "Acme", "summary": "Example"}
    similar_data = {"results": ["Acme Subsidiary"]}

    dossier_artifact = tmp_path / "dossier.json"
    similar_artifact = tmp_path / "similar.json"
    dossier_artifact.write_text(json.dumps(dossier_data))
    similar_artifact.write_text(json.dumps(similar_data))

    output_dir = tmp_path / "pdfs"
    result = convert_research_artifacts_to_pdfs(
        dossier_artifact,
        similar_artifact,
        output_dir=output_dir,
    )

    dossier_pdf = Path(result["dossier_pdf"])
    similar_pdf = Path(result["similar_companies_pdf"])

    assert dossier_pdf.exists()
    assert similar_pdf.exists()
    assert dossier_pdf.stat().st_size > 0
    assert similar_pdf.stat().st_size > 0


def test_convert_research_artifacts_accepts_mappings(tmp_path: Path) -> None:
    result = convert_research_artifacts_to_pdfs(
        {"company": "Example"},
        {"results": []},
        output_dir=tmp_path,
    )

    dossier_pdf = Path(result["dossier_pdf"])
    similar_pdf = Path(result["similar_companies_pdf"])

    assert dossier_pdf.name == "dossier_research.pdf"
    assert similar_pdf.name == "similar_companies.pdf"
    assert dossier_pdf.exists()
    assert similar_pdf.exists()
