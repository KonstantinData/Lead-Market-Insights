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

    def evaluate(self, context: Dict) -> Tuple[bool, str]:
        # Notes: 1) Missing critical fields
        missing = [field for field in self.required_fields if not context.get(field)]
        if missing:
            return True, f"Missing fields: {', '.join(missing)}"

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

        return False, "All checks passed"
