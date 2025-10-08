from __future__ import annotations

import pytest

from agents.hitl_decision_evaluator import HITLDecisionEvaluator


@pytest.fixture()
def evaluator() -> HITLDecisionEvaluator:
    return HITLDecisionEvaluator()


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {
                "company_domain": "acme.test",
                "company_in_crm": True,
                "attachments_in_crm": False,
            },
            "CRM company missing attachments",
        ),
        (
            {"company_domain": "acme.test", "insufficient_context": True},
            "Dossier research reported insufficient_context",
        ),
        (
            {
                "company_domain": "acme.test",
                "missing_fields": ["industry_group", "description"],
            },
            "Missing fields require human input",
        ),
    ],
)
def test_hitl_required_core_rules(
    evaluator: HITLDecisionEvaluator, payload: dict, expected: str
) -> None:
    hitl_required, reason = evaluator.requires_hitl(payload)

    assert hitl_required is True
    assert expected in reason


def test_hitl_not_required_when_context_valid(evaluator: HITLDecisionEvaluator) -> None:
    hitl_required, reason = evaluator.requires_hitl(
        {"company_domain": "acme.test", "confidence_score": 0.95}
    )

    assert hitl_required is False
    assert reason == "All checks passed"
