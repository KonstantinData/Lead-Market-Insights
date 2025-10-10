"""
HITL contracts — strict Pydantic v2 models.
"""
from __future__ import annotations
from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


SCHEMA_VERSION = "1.0"


# Explanation: UTC timestamp helper


def now_iso() -> str:
return datetime.now(timezone.utc).isoformat()




class MaskedPayload(BaseModel):
model_config = ConfigDict(extra="forbid", validate_assignment=True)
schema_version: str = Field(default=SCHEMA_VERSION)
run_id: str
data: Dict[str, Any]
pii_redaction: str




DecisionType = Literal["APPROVED", "DECLINED", "CHANGE_REQUESTED"]




class HitlRequest(BaseModel):
model_config = ConfigDict(extra="forbid", validate_assignment=True)
schema_version: str = Field(default=SCHEMA_VERSION)
run_id: str
subject: str
context: Dict[str, Any]
masked_payload: MaskedPayload
msg_id: Optional[str] = None
created_at: str = Field(default_factory=now_iso)




class HitlDecision(BaseModel):
model_config = ConfigDict(extra="forbid", validate_assignment=True)
schema_version: str = Field(default=SCHEMA_VERSION)
run_id: str
decision: DecisionType
actor: str
kv: Dict[str, Any] = Field(default_factory=dict)
msg_id: Optional[str] = None
decided_at: str = Field(default_factory=now_iso)




class AuditEvent(BaseModel):
model_config = ConfigDict(extra="forbid", validate_assignment=True)
schema_version: str = Field(default=SCHEMA_VERSION)
run_id: str
event: str
details: Dict[str, Any] = Field(default_factory=dict)
ts: str = Field(default_factory=now_iso)
prev_hash: Optional[str] = None