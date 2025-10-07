from pydantic import BaseModel, Field
from typing import List, Dict


class CompanyAnalysisContext(BaseModel):
    company_name: str
    country: str = "DE"
    legal_entity: str = ""
    register_id: str = ""
    hq_city: str = ""
    hq_country: str = "DE"
    rev_ttm: str = ""
    ebitda_margin: str = ""
    nd_ebitda: str = ""
    top_competitors: List[str] = []
    product_portfolio: str = ""
    product_pipeline: str = ""
    plants: str = ""
    lead_times: str = ""
    csrd_status: str = ""
    lksg_status: str = ""
    press_sentiment: str = ""
    top_news: str = ""
    price_levers: str = ""
    payment_levers: str = ""
    risk_1: str = ""
    risk_1_lvl: str = ""
    risk_2: str = ""
    risk_2_lvl: str = ""
    risk_3: str = ""
    risk_3_lvl: str = ""
    overall_score: float = Field(ge=0, le=5, default=0.0)
    traffic_light: str = "Y"
    key_insight_1: str = ""
    key_insight_2: str = ""
    key_insight_3: str = ""
