"""Strict Pydantic models shared across the standalone HITL components."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SCHEMA_VERSION = "1.0"


def now_iso() -> str:
    """Return a UTC timestamp in ISO-8601 format."""

    return datetime.now(timezone.utc).isoformat()


class MaskedPayload(BaseModel):
    """Envelope storing a redacted representation of user supplied context."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str
    data: Dict[str, Any]
    pii_redaction: str


DecisionType = Literal["APPROVED", "DECLINED", "CHANGE_REQUESTED"]


class HitlRequest(BaseModel):
    """Persisted representation of a HITL request sent to an operator."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str
    subject: str
    context: Dict[str, Any]
    masked_payload: MaskedPayload
    msg_id: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)


class HitlDecision(BaseModel):
    """Normalised organiser reply processed by the HITL orchestrator."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str
    decision: DecisionType
    actor: str
    kv: Dict[str, Any] = Field(default_factory=dict)
    msg_id: Optional[str] = None
    decided_at: str = Field(default_factory=now_iso)


class AuditEvent(BaseModel):
    """Append-only audit event persisted alongside the HITL state."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: str = Field(default=SCHEMA_VERSION)
    run_id: str
    event: str
    details: Dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=now_iso)
    prev_hash: Optional[str] = None