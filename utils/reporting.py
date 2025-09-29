"""Utilities for converting research artefacts into PDF documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Sequence, Union

try:  # pragma: no cover - import guard for environments without ReportLab
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas
    _REPORTLAB_IMPORT_ERROR: Optional[ImportError] = None
except ImportError as exc:  # pragma: no cover - captured for graceful error reporting
    LETTER = (612.0, 792.0)  # type: ignore[assignment]
    inch = 72.0  # type: ignore[assignment]
    simpleSplit = None  # type: ignore[assignment]
    canvas = None  # type: ignore[assignment]
    _REPORTLAB_IMPORT_ERROR = exc

from config.config import settings

JsonLike = Union[str, Path, Mapping[str, Any]]


def convert_research_artifacts_to_pdfs(
    dossier_artifact: JsonLike,
    similar_companies_artifact: JsonLike,
    *,
    output_dir: Optional[Union[str, Path]] = None,
) -> MutableMapping[str, str]:
    """Convert dossier and similar company JSON payloads into PDF files.

    Parameters
    ----------
    dossier_artifact:
        Mapping or path pointing to the dossier research JSON artefact.
    similar_companies_artifact:
        Mapping or path pointing to the similar companies JSON artefact.
    output_dir:
        Optional override for the directory where the PDF files will be written.

    Returns
    -------
    dict
        Mapping containing the file paths to the generated dossier and similar
        companies PDFs. Paths are returned as POSIX strings for portability.
    """

    target_dir = Path(output_dir or settings.research_pdf_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    dossier_payload = _load_json_payload(dossier_artifact)
    similar_payload = _load_json_payload(similar_companies_artifact)

    if _REPORTLAB_IMPORT_ERROR is not None:
        raise ImportError(
            "ReportLab is required to generate research PDFs. "
            "Install the 'reportlab' package to enable reporting support."
        ) from _REPORTLAB_IMPORT_ERROR

    dossier_pdf = target_dir / _resolve_pdf_name(dossier_artifact, "dossier_research")
    similar_pdf = target_dir / _resolve_pdf_name(
        similar_companies_artifact, "similar_companies"
    )

    _write_json_pdf("Dossier Research", dossier_payload, dossier_pdf)
    _write_json_pdf("Similar Companies", similar_payload, similar_pdf)

    return {
        "dossier_pdf": dossier_pdf.as_posix(),
        "similar_companies_pdf": similar_pdf.as_posix(),
    }


def _load_json_payload(source: JsonLike) -> Mapping[str, Any]:
    if isinstance(source, Mapping):
        return source
    path = Path(source)
    data = path.read_text(encoding="utf-8")
    return json.loads(data)


def _resolve_pdf_name(source: JsonLike, fallback: str) -> str:
    if isinstance(source, Mapping):
        return f"{fallback}.pdf"
    stem = Path(source).stem
    if not stem:
        return f"{fallback}.pdf"
    return f"{stem}.pdf"


def _write_json_pdf(title: str, payload: Mapping[str, Any], output_path: Path) -> None:
    if _REPORTLAB_IMPORT_ERROR is not None:  # pragma: no cover - defensive guard
        raise ImportError(
            "ReportLab dependency missing; unable to generate PDF output."
        ) from _REPORTLAB_IMPORT_ERROR

    document = canvas.Canvas(str(output_path), pagesize=LETTER)
    width, height = LETTER

    header_text = document.beginText()
    header_text.setFont("Helvetica-Bold", 14)
    header_text.setTextOrigin(0.75 * inch, height - 0.75 * inch)
    header_text.textLine(title)
    header_text.setFont("Helvetica", 10)
    header_text.textLine("")

    json_lines = json.dumps(payload, indent=2, ensure_ascii=False).splitlines()

    max_width = width - (1.5 * inch)
    current_text = header_text

    for line in json_lines:
        wrapped = simpleSplit(line, "Helvetica", 10, max_width)
        for chunk in wrapped or [""]:
            if current_text.getY() <= 0.75 * inch:
                document.drawText(current_text)
                document.showPage()
                current_text = document.beginText()
                current_text.setTextOrigin(0.75 * inch, height - 0.75 * inch)
                current_text.setFont("Helvetica", 10)
            current_text.textLine(chunk)

    document.drawText(current_text)
    document.save()


__all__: Sequence[str] = ["convert_research_artifacts_to_pdfs"]
