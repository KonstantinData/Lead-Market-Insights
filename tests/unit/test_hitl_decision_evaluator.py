from agents.hitl_decision_evaluator import HITLDecisionEvaluator


def test_hitl_required_missing_fields():
    ev = HITLDecisionEvaluator()
    hitl, reason = ev.evaluate({"company_domain": ""})
    assert hitl is True and "Missing fields" in reason


def test_hitl_required_low_confidence():
    ev = HITLDecisionEvaluator(confidence_threshold=0.9)
    hitl, reason = ev.evaluate({"company_domain": "acme.test", "confidence_score": 0.5})
    assert hitl is True and "Low confidence" in reason


def test_hitl_required_crm_attachments():
    ev = HITLDecisionEvaluator()
    hitl, reason = ev.evaluate({
        "company_domain": "acme.test",
        "company_in_crm": True,
        "attachments_in_crm": True,
    })
    assert hitl is True and "attachments" in reason


def test_no_hitl_all_good():
    ev = HITLDecisionEvaluator()
    hitl, reason = ev.evaluate({"company_domain": "acme.test", "confidence_score": 0.95})
    assert hitl is False and reason == "All checks passed"
