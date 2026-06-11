"""
Tests for Feature 2 (coupon_hunter agent) — web search, coupon extraction,
deduplication, and validity filtering. All network and LLM calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.coupon_hunter import CouponHunter
from models.coupon import Coupon, CouponSearchResult
from models.product import SelectedProduct


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hunter() -> CouponHunter:
    return CouponHunter()


@pytest.fixture
def sample_products() -> list[SelectedProduct]:
    return [
        SelectedProduct(
            product_name="Bounty Select-A-Size Paper Towels 12pk",
            price=19.97,
            in_stock=True,
            product_url="https://www.walmart.com/ip/bounty",
            recommended_quantity=2,
            deal_applied="Buy 2 Get 1 Free",
            effective_total=39.94,
            estimated_savings=19.97,
            reasoning="Best rated with BOGO deal.",
        ),
        SelectedProduct(
            product_name="Softsoap Hand Soap 11 oz Pack of 3",
            price=9.47,
            in_stock=True,
            product_url="https://www.walmart.com/ip/softsoap",
            recommended_quantity=1,
            effective_total=9.47,
            estimated_savings=0.0,
            reasoning="Good value hand soap.",
        ),
    ]


@pytest.fixture
def sample_snippets() -> list[str]:
    return [
        "RetailMeNot — Walmart promo codes June 2026\n"
        "Use code SAVE20 at checkout for 20% off your entire order. Min $50.",
        "Slickdeals — Walmart free shipping code\n"
        "Code FREESHIP works on orders over $35. Verified yesterday.",
        "Honey — Walmart deals June 2026\n"
        "SAVE20 gives 20% off. Also try WALMART10 for $10 off orders over $75.",
    ]


@pytest.fixture
def two_coupon_llm_response() -> list[dict]:
    return [
        {
            "coupon_code": "SAVE20",
            "discount_type": "percentage",
            "discount_value": "20% off",
            "conditions": "Minimum $50",
            "likely_valid": True,
            "source": "RetailMeNot",
            "source_url": "https://retailmenot.com/walmart",
        },
        {
            "coupon_code": "FREESHIP",
            "discount_type": "free_shipping",
            "discount_value": "Free shipping",
            "conditions": "Orders over $35",
            "likely_valid": True,
            "source": "Slickdeals",
            "source_url": None,
        },
    ]


# ---------------------------------------------------------------------------
# Core hunt() tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hunt_returns_coupon_search_result(
    hunter, sample_products, sample_snippets, two_coupon_llm_response
):
    """hunt() should return a CouponSearchResult with 2 valid coupons."""
    with patch.object(
        hunter._scraper, "search_coupons", new=AsyncMock(return_value=sample_snippets)
    ):
        with patch(
            "agents.coupon_hunter.call_claude",
            new=AsyncMock(return_value=two_coupon_llm_response),
        ):
            result = await hunter.hunt("walmart", sample_products)

    assert isinstance(result, CouponSearchResult)
    assert result.store == "walmart"
    assert len(result.coupons) == 2
    assert all(isinstance(c, Coupon) for c in result.coupons)
    codes = {c.coupon_code for c in result.coupons}
    assert "SAVE20" in codes
    assert "FREESHIP" in codes


@pytest.mark.asyncio
async def test_hunt_deduplicates_same_code(hunter, sample_products, sample_snippets):
    """If the LLM returns the same code twice, the result should only contain it once."""
    duplicate_response = [
        {
            "coupon_code": "SAVE20",
            "discount_type": "percentage",
            "discount_value": "20% off",
            "conditions": None,
            "likely_valid": True,
            "source": "RetailMeNot",
            "source_url": None,
        },
        {
            "coupon_code": "save20",  # same code, different case
            "discount_type": "percentage",
            "discount_value": "20% off",
            "conditions": "Min $50",
            "likely_valid": True,
            "source": "Honey",
            "source_url": None,
        },
    ]
    with patch.object(
        hunter._scraper, "search_coupons", new=AsyncMock(return_value=sample_snippets)
    ):
        with patch(
            "agents.coupon_hunter.call_claude",
            new=AsyncMock(return_value=duplicate_response),
        ):
            result = await hunter.hunt("walmart", sample_products)

    assert len(result.coupons) == 1
    assert result.coupons[0].coupon_code == "SAVE20"


@pytest.mark.asyncio
async def test_hunt_filters_invalid_coupons(hunter, sample_products, sample_snippets):
    """Coupons with likely_valid=False should be excluded from the result."""
    mixed_response = [
        {
            "coupon_code": "VALID10",
            "discount_type": "percentage",
            "discount_value": "10% off",
            "conditions": None,
            "likely_valid": True,
            "source": "RetailMeNot",
            "source_url": None,
        },
        {
            "coupon_code": "EXPIRED99",
            "discount_type": "percentage",
            "discount_value": "99% off",
            "conditions": None,
            "likely_valid": False,  # should be filtered out
            "source": "SomeSketchySite",
            "source_url": None,
        },
    ]
    with patch.object(
        hunter._scraper, "search_coupons", new=AsyncMock(return_value=sample_snippets)
    ):
        with patch(
            "agents.coupon_hunter.call_claude",
            new=AsyncMock(return_value=mixed_response),
        ):
            result = await hunter.hunt("walmart", sample_products)

    assert len(result.coupons) == 1
    assert result.coupons[0].coupon_code == "VALID10"


@pytest.mark.asyncio
async def test_hunt_records_search_queries(
    hunter, sample_products, sample_snippets, two_coupon_llm_response
):
    """hunt() should record which search queries were used."""
    with patch.object(
        hunter._scraper, "search_coupons", new=AsyncMock(return_value=sample_snippets)
    ):
        with patch(
            "agents.coupon_hunter.call_claude",
            new=AsyncMock(return_value=two_coupon_llm_response),
        ):
            result = await hunter.hunt("walmart", sample_products)

    assert len(result.search_queries_used) > 0


# ---------------------------------------------------------------------------
# Resilience / error-path tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hunt_returns_empty_when_scraper_fails(hunter, sample_products):
    """If the scraper raises, hunt() must not crash and returns empty coupons."""
    with patch.object(
        hunter._scraper,
        "search_coupons",
        new=AsyncMock(side_effect=Exception("network error")),
    ):
        result = await hunter.hunt("walmart", sample_products)

    assert isinstance(result, CouponSearchResult)
    assert result.coupons == []


@pytest.mark.asyncio
async def test_hunt_returns_empty_when_llm_fails(hunter, sample_products, sample_snippets):
    """If the LLM call raises, hunt() must not crash and returns empty coupons."""
    with patch.object(
        hunter._scraper, "search_coupons", new=AsyncMock(return_value=sample_snippets)
    ):
        with patch(
            "agents.coupon_hunter.call_claude",
            new=AsyncMock(side_effect=Exception("API timeout")),
        ):
            result = await hunter.hunt("walmart", sample_products)

    assert isinstance(result, CouponSearchResult)
    assert result.coupons == []


@pytest.mark.asyncio
async def test_hunt_handles_empty_product_list(hunter):
    """hunt() with an empty products list should return an empty CouponSearchResult."""
    result = await hunter.hunt("walmart", [])
    assert isinstance(result, CouponSearchResult)
    assert result.coupons == []


@pytest.mark.asyncio
async def test_hunt_handles_no_snippets(hunter, sample_products):
    """If all searches return empty, the LLM should not be called."""
    with patch.object(
        hunter._scraper, "search_coupons", new=AsyncMock(return_value=[])
    ):
        with patch(
            "agents.coupon_hunter.call_claude", new=AsyncMock()
        ) as mock_llm:
            result = await hunter.hunt("walmart", sample_products)

    mock_llm.assert_not_called()
    assert result.coupons == []
