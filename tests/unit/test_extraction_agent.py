import pytest

from agents.extraction_agent import ExtractionAgent


@pytest.mark.asyncio
async def test_extract_derives_company_from_detected_domain():
    agent = ExtractionAgent()
    event = {
        "summary": "product roadmap review",
        "description": "Exciting discussion with Example Labs about next steps. Visit examplelabs.io for details.",
    }

    result = await agent.extract(event)

    assert result["info"]["web_domain"] == "examplelabs.io"
    assert result["info"]["company_name"] == "Examplelabs"


@pytest.mark.asyncio
async def test_extract_ignores_capitalised_adjectives_in_description():
    agent = ExtractionAgent()
    event = {
        "summary": "first strategy touchpoint with example labs",
        "description": "Exciting Conversation With Example Labs leadership on progress.",
    }

    result = await agent.extract(event)

    assert result["info"]["company_name"] == "Example Labs"
    assert result["info"]["web_domain"] is None
