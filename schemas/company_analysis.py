"""Schemas describing company analysis payloads."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class CompanyAnalysis(TypedDict, total=False):
    """TypedDict describing structured company analysis output."""

    company_name: str
    company_domain: Optional[str]
    web_domain: Optional[str]
    summary: Optional[str]
    highlights: List[str]
    metadata: Dict[str, str]


__all__ = ["CompanyAnalysis"]
