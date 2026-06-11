"""
Main orchestrator agent — coordinates Feature 1 (product selection),
Feature 2 (coupon discovery), and Feature 3 (browser execution) into a single flow.
"""

from __future__ import annotations

from rich.panel import Panel

from agents.browser_agent import BrowserAgent
from agents.coupon_hunter import CouponHunter
from agents.product_selector import ProductSelector
from models.cart import Cart, CartItem, CartSummary
from models.coupon import CouponSearchResult
from models.product import SelectedProduct
from utils.browser import get_browser, get_page
from utils.logger import (
    _con,
    get_logger,
    log_agent_action,
    log_agent_thinking,
    log_cart_summary,
    log_error,
    setup_logger,
)


class SmartCartOrchestrator:

    def __init__(self) -> None:
        setup_logger()
        self._logger = get_logger(__name__)
        self._product_selector = ProductSelector()
        self._coupon_hunter = CouponHunter()
        self._browser_agent = BrowserAgent()

    async def run(self, user_request: str) -> CartSummary:
        # ── Banner ──────────────────────────────────────────────────────────
        _con().print(Panel(
            f"[bold white]{user_request}[/bold white]",
            title="[bold cyan]🚀  SmartCart Agent Starting[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        ))

        selected_products: list[SelectedProduct] = []
        coupon_result = CouponSearchResult(store="walmart")
        cart = Cart()

        # ── Phase 1: Product Selection ───────────────────────────────────────
        try:
            async with get_browser() as browser:
                async with get_page(browser) as sp:

                    log_agent_thinking(
                        "Orchestrator",
                        "Phase 1 — Parsing request and selecting best products…",
                    )
                    selected_products = await self._product_selector.process_request(
                        user_request, sp.page
                    )

                    if not selected_products:
                        log_error("No products could be selected — aborting.")
                        return CartSummary(cart=Cart())

                    log_agent_action(
                        "Orchestrator",
                        f"Selected {len(selected_products)} product(s). "
                        "Now hunting for coupons…",
                    )

                    # ── Phase 2: Coupon Discovery ────────────────────────────
                    try:
                        log_agent_thinking(
                            "Orchestrator",
                            "Phase 2 — Searching the web for coupon codes…",
                        )
                        coupon_result = await self._coupon_hunter.hunt(
                            "walmart", selected_products
                        )
                        if coupon_result.coupons:
                            log_agent_action(
                                "Orchestrator",
                                f"Found {len(coupon_result.coupons)} valid coupon(s): "
                                + ", ".join(c.coupon_code for c in coupon_result.coupons),
                            )
                        else:
                            log_agent_action(
                                "Orchestrator",
                                "No valid coupons found — continuing without discount codes.",
                            )
                    except Exception as exc:
                        log_error(f"Coupon hunting failed ({exc}) — continuing without coupons")
                        self._logger.exception(exc)

                    # ── Phase 3: Browser Execution ───────────────────────────
                    log_agent_thinking(
                        "Orchestrator",
                        "Phase 3 — Executing purchase. Watch the browser…",
                    )
                    try:
                        cart = await self._browser_agent.execute_purchase(
                            sp, selected_products, coupon_result.coupons
                        )
                    except Exception as exc:
                        log_error(f"Browser execution failed ({exc}) — building summary from selections")
                        self._logger.exception(exc)
                        cart = _cart_from_selections(selected_products)

        except Exception as exc:
            log_error(f"Orchestrator fatal error: {exc}")
            self._logger.exception(exc)
            # If we have selections, still build a meaningful summary
            if selected_products:
                cart = _cart_from_selections(selected_products)

        finally:
            await self._coupon_hunter.close()

        # ── Build and display CartSummary ───────────────────────────────────
        summary = CartSummary(cart=cart)
        log_cart_summary(summary)
        return summary


# ---------------------------------------------------------------------------
# Helper: build a Cart directly from selected products (no browser required)
# ---------------------------------------------------------------------------

def _cart_from_selections(products: list[SelectedProduct]) -> Cart:
    """Construct a best-estimate Cart when the browser phase fails or is skipped."""
    items = [
        CartItem(
            product=p,
            quantity_added=p.recommended_quantity,
            line_total=p.effective_total,
        )
        for p in products
    ]
    return Cart(items=items)
