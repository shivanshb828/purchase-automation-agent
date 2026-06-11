"""
Tests for Feature 3 (browser_agent) — execute_purchase orchestration.
All Playwright and browser interactions are mocked; tests verify call counts,
argument values, and resilience when individual steps fail.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from agents.browser_agent import BrowserAgent, _parse_price
from models.cart import Cart, CartItem
from models.coupon import Coupon
from models.product import SelectedProduct


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agent() -> BrowserAgent:
    return BrowserAgent()


@pytest.fixture
def mock_sp() -> MagicMock:
    """Minimal SmartPage mock — all async helpers succeed by default."""
    sp = MagicMock()
    sp.goto = AsyncMock()
    sp.safe_click = AsyncMock(return_value=True)
    sp.safe_type = AsyncMock(return_value=True)
    sp.wait_and_extract = AsyncMock(return_value=None)
    sp.take_screenshot = AsyncMock(return_value=Path("test.png"))
    sp.page = MagicMock()
    sp.page.wait_for_selector = AsyncMock()
    sp.page.keyboard = MagicMock()
    sp.page.keyboard.press = AsyncMock()
    sp.page.locator = MagicMock(return_value=MagicMock(all=AsyncMock(return_value=[])))
    return sp


@pytest.fixture
def two_products() -> list[SelectedProduct]:
    return [
        SelectedProduct(
            product_name="Bounty Select-A-Size Paper Towels 12pk",
            price=19.97,
            in_stock=True,
            product_url="https://www.walmart.com/ip/bounty",
            recommended_quantity=2,
            effective_total=39.94,
            estimated_savings=19.97,
            reasoning="BOGO deal.",
        ),
        SelectedProduct(
            product_name="Softsoap Liquid Hand Soap Pack of 3",
            price=9.47,
            in_stock=True,
            product_url="https://www.walmart.com/ip/softsoap",
            recommended_quantity=1,
            effective_total=9.47,
            estimated_savings=0.0,
            reasoning="Good value.",
        ),
    ]


@pytest.fixture
def sample_coupon() -> Coupon:
    return Coupon(
        coupon_code="SAVE20",
        discount_type="percentage",
        discount_value="20% off",
        likely_valid=True,
        source="RetailMeNot",
    )


def _mock_all_steps(agent: BrowserAgent, *, find_returns=None) -> None:
    """Replace all BrowserAgent step methods with AsyncMocks on the instance."""
    agent.navigate_to_store = AsyncMock(return_value=True)
    agent.search_product = AsyncMock(return_value=True)
    agent.find_and_click_product = AsyncMock(
        return_value=True if find_returns is None else None,
        side_effect=find_returns,
    )
    agent.add_to_cart = AsyncMock(return_value=True)
    agent.go_to_cart = AsyncMock(return_value=True)
    agent.apply_coupon = AsyncMock(return_value=False)
    agent.scrape_cart = AsyncMock(return_value={"subtotal": 49.41, "total": 39.53})


# ---------------------------------------------------------------------------
# execute_purchase — call-count and argument tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_navigate_to_store_called_exactly_once(agent, mock_sp, two_products):
    """navigate_to_store must be called exactly once regardless of product count."""
    _mock_all_steps(agent)
    await agent.execute_purchase(mock_sp, two_products, [])
    agent.navigate_to_store.assert_called_once_with(mock_sp)


@pytest.mark.asyncio
async def test_search_product_called_once_per_product(agent, mock_sp, two_products):
    """search_product should be called once for each product."""
    _mock_all_steps(agent)
    await agent.execute_purchase(mock_sp, two_products, [])
    assert agent.search_product.call_count == len(two_products)
    names_searched = [c.args[1] for c in agent.search_product.call_args_list]
    assert names_searched[0] == two_products[0].product_name
    assert names_searched[1] == two_products[1].product_name


@pytest.mark.asyncio
async def test_add_to_cart_called_with_correct_quantity(agent, mock_sp, two_products):
    """add_to_cart must receive the recommended_quantity from each SelectedProduct."""
    _mock_all_steps(agent)
    await agent.execute_purchase(mock_sp, two_products, [])

    qtys = [c.args[1] for c in agent.add_to_cart.call_args_list]
    assert qtys[0] == two_products[0].recommended_quantity   # 2
    assert qtys[1] == two_products[1].recommended_quantity   # 1


@pytest.mark.asyncio
async def test_apply_coupon_called_per_coupon(agent, mock_sp, two_products, sample_coupon):
    """apply_coupon should be called once per coupon passed in."""
    _mock_all_steps(agent)
    extra_coupon = Coupon(
        coupon_code="FREESHIP",
        discount_type="free_shipping",
        discount_value="Free shipping",
        likely_valid=True,
    )
    result = await agent.execute_purchase(mock_sp, two_products, [sample_coupon, extra_coupon])
    assert agent.apply_coupon.call_count == 2
    codes_tried = [c.args[1] for c in agent.apply_coupon.call_args_list]
    assert "SAVE20" in codes_tried
    assert "FREESHIP" in codes_tried


# ---------------------------------------------------------------------------
# Resilience — partial failures must not abort the pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_find_skips_product_but_continues(agent, mock_sp, two_products):
    """If find_and_click_product fails for product 1, product 2 must still be added."""
    _mock_all_steps(agent)
    # Product 1 fails to find; product 2 succeeds
    agent.find_and_click_product = AsyncMock(side_effect=[False, True])

    result = await agent.execute_purchase(mock_sp, two_products, [])

    assert isinstance(result, Cart)
    # Only product 2 should be in cart
    assert len(result.items) == 1
    assert result.items[0].product.product_name == two_products[1].product_name
    # search_product still called for both
    assert agent.search_product.call_count == 2


@pytest.mark.asyncio
async def test_failed_search_skips_product_but_continues(agent, mock_sp, two_products):
    """If search_product fails for product 1, product 2 must still be processed."""
    _mock_all_steps(agent)
    agent.search_product = AsyncMock(side_effect=[False, True])

    result = await agent.execute_purchase(mock_sp, two_products, [])

    assert isinstance(result, Cart)
    assert len(result.items) == 1
    assert result.items[0].product.product_name == two_products[1].product_name


@pytest.mark.asyncio
async def test_execute_purchase_returns_empty_cart_on_store_failure(
    agent, mock_sp, two_products
):
    """If navigate_to_store fails, execute_purchase must return an empty Cart."""
    _mock_all_steps(agent)
    agent.navigate_to_store = AsyncMock(return_value=False)

    result = await agent.execute_purchase(mock_sp, two_products, [])

    assert isinstance(result, Cart)
    assert result.items == []
    agent.search_product.assert_not_called()


@pytest.mark.asyncio
async def test_successful_coupon_appears_in_coupons_succeeded(
    agent, mock_sp, two_products, sample_coupon
):
    """A coupon where apply_coupon returns True must appear in coupons_succeeded."""
    _mock_all_steps(agent)
    agent.apply_coupon = AsyncMock(return_value=True)

    result = await agent.execute_purchase(mock_sp, two_products, [sample_coupon])

    assert len(result.coupons_attempted) == 1
    assert len(result.coupons_succeeded) == 1
    assert result.coupons_succeeded[0].coupon_code == "SAVE20"


@pytest.mark.asyncio
async def test_go_to_cart_not_called_when_nothing_added(agent, mock_sp, two_products):
    """If every product fails to add, go_to_cart should not be called."""
    _mock_all_steps(agent)
    agent.add_to_cart = AsyncMock(return_value=False)

    await agent.execute_purchase(mock_sp, two_products, [])
    agent.go_to_cart.assert_not_called()


# ---------------------------------------------------------------------------
# Unit test: _parse_price helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("$47.50",        47.50),
    ("Subtotal $47.50", 47.50),
    ("$1,299.00",   1299.00),
    (None,            None),
    ("no price",      None),
])
def test_parse_price(text, expected):
    assert _parse_price(text) == expected
