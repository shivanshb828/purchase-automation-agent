"""
Pydantic models for coupon/promo data extracted from web search results.
"""

from __future__ import annotations

from pydantic import BaseModel


class Coupon(BaseModel):
    model_config = {"from_attributes": True}

    coupon_code: str
    discount_type: str           # "percentage" | "dollar_off" | "free_shipping" | "bogo"
    discount_value: str          # human-readable e.g. "20% off", "$5 off"
    conditions: str | None = None
    likely_valid: bool = True
    source: str | None = None
    source_url: str | None = None


class CouponSearchResult(BaseModel):
    model_config = {"from_attributes": True}

    store: str
    coupons: list[Coupon] = []
    search_queries_used: list[str] = []
