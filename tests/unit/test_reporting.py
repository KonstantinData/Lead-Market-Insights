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
    similar_data = {
        "results": ["Acme Subsidiary"],
        "metadata": {"link": "https://example.com"},
    }

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
    artifact_inputs: Tuple[object, object, Path],
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


def test_convert_research_artifacts_handles_hidden_file_names(tmp_path: Path) -> None:
    dossier_artifact = tmp_path / ".json"
    dossier_artifact.write_text(json.dumps({"company": "Example"}), encoding="utf-8")

    result = convert_research_artifacts_to_pdfs(
        dossier_artifact,
        {"results": []},
        output_dir=tmp_path,
    )

    dossier_pdf = Path(result["dossier_pdf"])
    assert dossier_pdf.name == ".json.pdf"


def test_convert_research_artifacts_triggers_page_break(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from utils import reporting

    page_breaks: list[bool] = []
    original_canvas = reporting.canvas.Canvas

    class TrackingCanvas(original_canvas):  # type: ignore[misc]
        def showPage(self) -> None:  # noqa: D401 - behaviour inherited
            page_breaks.append(True)
            super().showPage()

    monkeypatch.setattr(reporting.canvas, "Canvas", TrackingCanvas)

    dossier_payload = {"items": [f"entry {i}" for i in range(150)]}

    result = convert_research_artifacts_to_pdfs(
        dossier_payload,
        {"results": []},
        output_dir=tmp_path,
    )

    assert page_breaks, "Expected at least one page break for large payload"
    assert Path(result["dossier_pdf"]).exists()


def test_convert_research_artifacts_requires_reportlab(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("utils.reporting._REPORTLAB_IMPORT_ERROR", ImportError("missing"))

    with pytest.raises(ImportError) as exc:
        convert_research_artifacts_to_pdfs(
            {"company": "Example"},
            {"results": []},
            output_dir=tmp_path,
        )

    assert "ReportLab is required" in str(exc.value)
