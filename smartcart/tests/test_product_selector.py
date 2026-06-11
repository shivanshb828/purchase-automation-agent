"""
Tests for Feature 1 (product_selector agent) — query parsing, scraping,
and LLM-based product evaluation and selection.

LLM calls are mocked so tests run offline; Playwright scraping is tested
with a lightweight mock page that simulates the locator API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.product_selector import (
    ProductSelector,
    _parse_int,
    _parse_price,
    _parse_rating,
)
from models.product import ProductQuery, ScrapedProduct, SelectedProduct


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def selector() -> ProductSelector:
    return ProductSelector()


@pytest.fixture
def sample_products() -> list[ScrapedProduct]:
    return [
        ScrapedProduct(
            product_name="Bounty Select-A-Size Paper Towels, 12 Double Rolls",
            price=19.97,
            unit_price=None,
            rating=4.7,
            review_count=3241,
            deal_badge="Buy 2 Get 1 Free",
            in_stock=True,
            product_url="https://www.walmart.com/ip/bounty-12pk",
        ),
        ScrapedProduct(
            product_name="Great Value Paper Towels, 6 Rolls",
            price=8.49,
            unit_price=None,
            rating=4.2,
            review_count=312,
            deal_badge=None,
            in_stock=True,
            product_url="https://www.walmart.com/ip/gv-6pk",
        ),
        ScrapedProduct(
            product_name="Viva Multi-Surface Paper Towels, 6 Big Rolls",
            price=11.97,
            unit_price=None,
            rating=4.5,
            review_count=987,
            deal_badge="Rollback",
            in_stock=True,
            product_url="https://www.walmart.com/ip/viva-6pk",
        ),
    ]


@pytest.fixture
def selected_product_dict() -> dict:
    return {
        "product_name": "Bounty Select-A-Size Paper Towels, 12 Double Rolls",
        "price": 19.97,
        "unit_price": None,
        "rating": 4.7,
        "review_count": 3241,
        "deal_badge": "Buy 2 Get 1 Free",
        "in_stock": True,
        "product_url": "https://www.walmart.com/ip/bounty-12pk",
        "recommended_quantity": 2,
        "deal_applied": "Buy 2 Get 1 Free — third pack free",
        "effective_total": 39.94,
        "estimated_savings": 19.97,
        "reasoning": (
            "Bounty has 3241 reviews at 4.7 stars, far more reliable than alternatives. "
            "The Buy 2 Get 1 Free deal saves $19.97 on a regular consumable."
        ),
    }


# ---------------------------------------------------------------------------
# parse_request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_request_returns_product_queries(selector):
    mock_llm_response = [
        {"product_name": "paper towels", "category": "paper_goods", "consumable": True, "brand_preference": None},
        {"product_name": "liquid hand soap", "category": "hygiene", "consumable": True, "brand_preference": None},
        {"product_name": "goldfish crackers", "category": "food", "consumable": True, "brand_preference": None},
    ]
    with patch("agents.product_selector.call_claude", new=AsyncMock(return_value=mock_llm_response)):
        queries = await selector.parse_request(
            "I need paper towels, hand soap, and goldfish crackers for my daycare"
        )

    assert len(queries) == 3
    assert all(isinstance(q, ProductQuery) for q in queries)
    assert queries[0].product_name == "paper towels"
    assert queries[0].category == "paper_goods"
    assert queries[0].consumable is True
    assert queries[0].brand_preference is None
    assert queries[2].product_name == "goldfish crackers"


@pytest.mark.asyncio
async def test_parse_request_preserves_brand_preference(selector):
    mock_llm_response = [
        {"product_name": "Bounty paper towels", "category": "paper_goods",
         "consumable": True, "brand_preference": "Bounty"},
    ]
    with patch("agents.product_selector.call_claude", new=AsyncMock(return_value=mock_llm_response)):
        queries = await selector.parse_request("I need Bounty paper towels")

    assert queries[0].brand_preference == "Bounty"
    assert queries[0].product_name == "Bounty paper towels"


# ---------------------------------------------------------------------------
# evaluate_products
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_products_returns_selected_product(selector, sample_products, selected_product_dict):
    query = ProductQuery(product_name="paper towels", category="paper_goods", consumable=True)
    with patch("agents.product_selector.call_claude", new=AsyncMock(return_value=selected_product_dict)):
        selected = await selector.evaluate_products(sample_products, query)

    assert isinstance(selected, SelectedProduct)
    assert selected.product_name == "Bounty Select-A-Size Paper Towels, 12 Double Rolls"
    assert selected.recommended_quantity == 2
    assert selected.estimated_savings == 19.97
    assert selected.effective_total == 39.94
    assert selected.deal_applied == "Buy 2 Get 1 Free — third pack free"


@pytest.mark.asyncio
async def test_evaluate_products_deal_triggers_stocking_up(selector, sample_products, selected_product_dict):
    """When a BOGO deal is present, recommended_quantity should be > 1."""
    query = ProductQuery(product_name="paper towels", category="paper_goods", consumable=True)
    with patch("agents.product_selector.call_claude", new=AsyncMock(return_value=selected_product_dict)):
        selected = await selector.evaluate_products(sample_products, query)

    assert selected.recommended_quantity >= 2, "BOGO deal should trigger stocking up"


# ---------------------------------------------------------------------------
# search_and_scrape — mock the Playwright Page
# ---------------------------------------------------------------------------

def _make_card_mock(
    name: str,
    price_content: str,
    rating_label: str,
    review_text: str,
    deal_text: str | None = None,
    href: str = "/ip/test-product",
) -> MagicMock:
    """Build a mock Playwright locator that simulates a single product card."""
    def make_child(text: str | None = None, attr: str | None = None):
        loc = AsyncMock()
        loc.inner_text = AsyncMock(return_value=text or "")
        loc.get_attribute = AsyncMock(return_value=attr)
        return loc

    def locator_factory(selector: str):
        child = MagicMock()
        child.first = MagicMock()
        if 'product-title' in selector:
            child.first.inner_text = AsyncMock(return_value=name)
            child.first.get_attribute = AsyncMock(return_value=None)
        elif 'itemprop="price"' in selector:
            child.first.inner_text = AsyncMock(return_value="")
            child.first.get_attribute = AsyncMock(return_value=price_content)
        elif 'product-price' in selector:
            child.first.inner_text = AsyncMock(return_value=f"${price_content}")
            child.first.get_attribute = AsyncMock(return_value=None)
        elif 'unit-price' in selector:
            child.first.inner_text = AsyncMock(return_value="")
            child.first.get_attribute = AsyncMock(return_value=None)
        elif 'product-ratings' in selector and 'aria-label' in selector:
            child.first.inner_text = AsyncMock(return_value=rating_label)
            child.first.get_attribute = AsyncMock(return_value=rating_label)
        elif 'span.f7' in selector or 'review' in selector.lower():
            child.first.inner_text = AsyncMock(return_value=review_text)
            child.first.get_attribute = AsyncMock(return_value=None)
        elif 'out-of-stock' in selector:
            # Raise so _try_text returns None → in_stock stays True
            child.first.inner_text = AsyncMock(side_effect=Exception("not found"))
            child.first.get_attribute = AsyncMock(side_effect=Exception("not found"))
        elif 'deal-badge' in selector or 'promo-badge' in selector or 'badge' in selector:
            child.first.inner_text = AsyncMock(return_value=deal_text or "")
            child.first.get_attribute = AsyncMock(return_value=None)
        elif 'link-identifier' in selector or '/ip/' in selector:
            child.first.inner_text = AsyncMock(return_value="")
            child.first.get_attribute = AsyncMock(return_value=href)
        else:
            child.first.inner_text = AsyncMock(return_value="")
            child.first.get_attribute = AsyncMock(return_value=None)
        return child

    card = MagicMock()
    card.locator = MagicMock(side_effect=locator_factory)
    return card


@pytest.mark.asyncio
async def test_search_and_scrape_returns_empty_on_no_cards(selector):
    """If Walmart returns no product cards, return an empty list without crashing."""
    query = ProductQuery(product_name="unobtainium widget", category="other")

    page_mock = AsyncMock()
    page_mock.goto = AsyncMock()
    page_mock.wait_for_selector = AsyncMock(side_effect=Exception("Timeout: selector not found"))

    results = await selector.search_and_scrape(query, page_mock)
    assert results == []


@pytest.mark.asyncio
async def test_search_and_scrape_parses_card_correctly(selector):
    """A well-formed mock card should be extracted into a valid ScrapedProduct."""
    query = ProductQuery(product_name="paper towels", category="paper_goods")

    card = _make_card_mock(
        name="Bounty Select-A-Size 12pk",
        price_content="19.97",
        rating_label="4.7 out of 5 stars",
        review_text="3,241",
        deal_text="Buy 2 Get 1 Free",
        href="/ip/bounty-12pk",
    )

    page_mock = AsyncMock()
    page_mock.goto = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    cards_locator = AsyncMock()
    cards_locator.all = AsyncMock(return_value=[card])
    page_mock.locator = MagicMock(return_value=cards_locator)

    results = await selector.search_and_scrape(query, page_mock)

    assert len(results) == 1
    p = results[0]
    assert isinstance(p, ScrapedProduct)
    assert p.product_name == "Bounty Select-A-Size 12pk"
    assert p.price == 19.97
    assert p.rating == 4.7
    assert p.review_count == 3241
    assert p.deal_badge == "Buy 2 Get 1 Free"
    assert p.in_stock is True
    assert "/ip/bounty-12pk" in p.product_url


@pytest.mark.asyncio
async def test_search_and_scrape_skips_card_missing_price(selector):
    """Cards with no parseable price should be silently skipped."""
    query = ProductQuery(product_name="paper towels", category="paper_goods")

    bad_card = _make_card_mock(
        name="Mystery Product",
        price_content="",   # no price
        rating_label="",
        review_text="",
    )
    # Make price lookups fail
    def failing_locator(selector):
        child = MagicMock()
        child.first = MagicMock()
        if 'price' in selector.lower():
            child.first.get_attribute = AsyncMock(return_value=None)
            child.first.inner_text = AsyncMock(return_value="")
        elif 'product-title' in selector:
            child.first.inner_text = AsyncMock(return_value="Mystery Product")
            child.first.get_attribute = AsyncMock(return_value=None)
        else:
            child.first.inner_text = AsyncMock(return_value="")
            child.first.get_attribute = AsyncMock(return_value=None)
        return child
    bad_card.locator = MagicMock(side_effect=failing_locator)

    page_mock = AsyncMock()
    page_mock.goto = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()
    cards_locator = AsyncMock()
    cards_locator.all = AsyncMock(return_value=[bad_card])
    page_mock.locator = MagicMock(return_value=cards_locator)

    results = await selector.search_and_scrape(query, page_mock)
    assert results == []


# ---------------------------------------------------------------------------
# select_best_product — integration of scrape + evaluate (both mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_select_best_product_returns_none_on_empty_scrape(selector):
    query = ProductQuery(product_name="unobtainium", category="other")
    page_mock = AsyncMock()
    page_mock.goto = AsyncMock()
    page_mock.wait_for_selector = AsyncMock(side_effect=Exception("not found"))

    result = await selector.select_best_product(query, page_mock)
    assert result is None


@pytest.mark.asyncio
async def test_select_best_product_full_flow(selector, sample_products, selected_product_dict):
    """Mocks scrape + LLM evaluate — verifies the full select_best_product pipeline."""
    query = ProductQuery(product_name="paper towels", category="paper_goods", consumable=True)
    page_mock = AsyncMock()

    with patch.object(selector, "search_and_scrape", new=AsyncMock(return_value=sample_products)):
        with patch("agents.product_selector.call_claude", new=AsyncMock(return_value=selected_product_dict)):
            result = await selector.select_best_product(query, page_mock)

    assert isinstance(result, SelectedProduct)
    assert result.estimated_savings > 0
    assert result.recommended_quantity == 2


# ---------------------------------------------------------------------------
# Pure parsing helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("$16.97",          16.97),
    ("Now $16.97 each", 16.97),
    ("From $8.49",       8.49),
    ("$1,299.00",     1299.00),
    ("No price here",    None),
])
def test_parse_price(text, expected):
    assert _parse_price(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("4.7 out of 5 stars", 4.7),
    ("4 out of 5 stars",   4.0),
    ("3.8 out of 5",       3.8),
    ("",                   None),
])
def test_parse_rating(text, expected):
    assert _parse_rating(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("3,241",          3241),
    ("3241 reviews",   3241),
    ("(142)",           142),
    ("no numbers here", None),
])
def test_parse_int(text, expected):
    assert _parse_int(text) == expected
