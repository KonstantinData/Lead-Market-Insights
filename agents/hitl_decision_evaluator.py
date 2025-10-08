from __future__ import annotations

from typing import Dict, Sequence, Tuple


class HITLDecisionEvaluator:
    """
    # Notes:
    # - Centralized logic whether a human-in-the-loop step is required.
    # - Returns (hitl_required: bool, reason: str)
    # - Easily extensible with new rules, weights, or ML-based confidence.
    """

    def __init__(
        self,
        *,
        confidence_threshold: float = 0.80,
        required_fields: Sequence[str] = ("company_domain",),
        crm_attachment_rule: bool = True,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.required_fields = tuple(required_fields)
        self.crm_attachment_rule = crm_attachment_rule

    def requires_hitl(self, context: Dict) -> Tuple[bool, str]:
        """Return whether the supplied *context* requires human review."""

        # Notes: 1) Missing critical fields
        missing = [field for field in self.required_fields if not context.get(field)]
        if missing:
            return True, f"Missing fields: {', '.join(missing)}"

        optional_missing = context.get("missing_optional_fields")
        if optional_missing:
            if not isinstance(optional_missing, (list, tuple, set)):
                optional_missing = [optional_missing]
            formatted = ", ".join(str(item) for item in optional_missing if item)
            if not formatted:
                formatted = "optional fields"
            return True, f"Missing optional fields: {formatted}"

        if context.get("insufficient_context"):
            return True, "Dossier research reported insufficient_context"

        missing_required = context.get("missing_fields") or []
        if isinstance(missing_required, (list, tuple)) and len(missing_required) > 0:
            return True, "Missing fields require human input: " + ", ".join(
                map(str, missing_required)
            )
        if missing_required and not isinstance(missing_required, (list, tuple)):
            return True, f"Missing fields require human input: {missing_required}"

        # Notes: 2) Low confidence from upstream extraction/classification
        confidence = context.get("confidence_score")
        if confidence is not None and confidence < self.confidence_threshold:
            return True, f"Low confidence score: {confidence} < {self.confidence_threshold}"

        # Notes: 3) CRM attachments require human review (if enabled)
        if (
            self.crm_attachment_rule
            and context.get("company_in_crm")
            and context.get("attachments_in_crm")
        ):
            return True, "CRM attachments require review"

        if context.get("company_in_crm") and context.get("attachments_in_crm") is False:
            return True, "CRM company missing attachments"

        dossier_status = context.get("dossier_status")
        if isinstance(dossier_status, str) and dossier_status.lower() == "insufficient_context":
            return True, "Dossier research returned insufficient context"

        return False, "All checks passed"

    def evaluate(self, context: Dict) -> Tuple[bool, str]:
        """Backward compatible alias for :meth:`requires_hitl`."""

        return self.requires_hitl(context)
