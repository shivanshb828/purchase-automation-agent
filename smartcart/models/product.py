"""
Pydantic models for product data: scraped search results, LLM-selected product,
and parsed product query from user request.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ScrapedProduct(BaseModel):
    model_config = {"from_attributes": True}

    product_name: str
    price: float
    unit_price: float | None = None
    rating: float | None = None
    review_count: int | None = None
    deal_badge: str | None = None
    in_stock: bool = True
    product_url: str


class SelectedProduct(ScrapedProduct):
    """ScrapedProduct extended with LLM evaluation output."""

    recommended_quantity: int = Field(default=1, ge=1)
    deal_applied: str | None = None
    effective_total: float = 0.0
    estimated_savings: float = 0.0
    reasoning: str = ""

    @model_validator(mode="after")
    def set_effective_total_default(self) -> SelectedProduct:
        if self.effective_total == 0.0:
            self.effective_total = self.price * self.recommended_quantity
        return self


class ProductQuery(BaseModel):
    model_config = {"from_attributes": True}

    product_name: str
    category: str
    consumable: bool = True
    brand_preference: str | None = None
