from human_in_the_loop.hitl_module import HumanInTheLoop, HitlDecision


def test_hitl_no_auto_approval():
    hitl = HumanInTheLoop()
    decision = hitl.request_approval({"x": 1})
    assert isinstance(decision, HitlDecision)
    assert decision.status is None
    assert decision.payload == {"x": 1}


def test_hitl_request_info_pending():
    hitl = HumanInTheLoop()
    decision = hitl.request_info({"event": "foo"}, {"missing": "bar"})
    assert isinstance(decision, HitlDecision)
    assert decision.status is None
    assert decision.payload == {"event": {"event": "foo"}, "missing": {"missing": "bar"}}
