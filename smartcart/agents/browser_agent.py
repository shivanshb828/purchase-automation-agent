"""
Feature 3 agent — drives the Playwright browser to search, navigate, add products
to cart, apply coupons, and return a final cart summary for user approval.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse

from models.cart import Cart, CartItem
from models.coupon import Coupon
from models.product import SelectedProduct
from utils.browser import SmartPage, dismiss_popups
from utils.logger import (
    get_logger,
    log_agent_action,
    log_agent_thinking,
    log_coupon_result,
    log_error,
)
from config import get_store, APP, BROWSER


class BrowserAgent:

    def __init__(self) -> None:
        self._sel = get_store().selectors
        self._logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Step 1 — Store navigation
    # ------------------------------------------------------------------

    async def navigate_to_store(self, sp: SmartPage) -> bool:
        try:
            store = get_store()
            log_agent_action("Browser Agent", f"Navigating to {store.base_url}")
            await sp.goto(store.base_url)
            await dismiss_popups(sp.page)
            await sp.take_screenshot("store_loaded")
            return True
        except Exception as exc:
            log_error(f"navigate_to_store failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Step 2 — Search
    # ------------------------------------------------------------------

    async def search_product(self, sp: SmartPage, product_name: str) -> bool:
        log_agent_action("Browser Agent", f'Searching for "{product_name}"')
        try:
            typed = await sp.safe_type(self._sel["search_bar"], product_name)
            if typed:
                await sp.page.keyboard.press("Enter")
            else:
                # Fallback: navigate to search URL directly
                encoded = urllib.parse.quote_plus(product_name)
                await sp.goto(get_store().search_url_template.format(query=encoded))

            await sp.page.wait_for_selector(self._sel["product_card"], timeout=12_000)
            safe_name = product_name[:20].replace(" ", "_")
            await sp.take_screenshot(f"search_results_{safe_name}")
            return True
        except Exception as exc:
            log_error(f"search_product failed for '{product_name}': {exc}")
            await sp.take_screenshot(f"search_failed_{product_name[:15].replace(' ', '_')}")
            return False

    # ------------------------------------------------------------------
    # Step 3 — Find and click the right product card
    # ------------------------------------------------------------------

    async def find_and_click_product(
        self, sp: SmartPage, target: SelectedProduct
    ) -> bool:
        log_agent_action(
            "Browser Agent", f'Finding: "{target.product_name[:55]}"'
        )
        try:
            cards = await sp.page.locator(self._sel["product_card"]).all()
            target_lower = target.product_name.lower()
            target_words = set(target_lower.split())

            best_card = None
            best_score = 0

            for card in cards[:10]:
                try:
                    title = await card.locator(
                        self._sel["product_title"]
                    ).first.inner_text(timeout=2_000)
                    title_lower = title.lower()

                    # Substring match wins immediately
                    if target_lower in title_lower or title_lower in target_lower:
                        best_card = card
                        best_score = 999
                        break

                    overlap = len(target_words & set(title_lower.split()))
                    if overlap > best_score:
                        best_score = overlap
                        best_card = card
                except Exception:
                    continue

            # Fall back to first card if nothing scored ≥ 3 words
            if best_score < 3 and cards:
                best_card = cards[0]

            if not best_card:
                log_error(f"No product cards found for '{target.product_name}'")
                return False

            # Click the product link inside the card
            clicked = False
            for link_sel in (self._sel["product_link"], 'a[href*="/ip/"]'):
                try:
                    link = best_card.locator(link_sel).first
                    await link.click(timeout=6_000)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                await best_card.click(timeout=6_000)

            # Wait for detail page to show the product title
            try:
                await sp.page.wait_for_selector(
                    self._sel["detail_title"], timeout=10_000
                )
            except Exception:
                pass  # Some product pages use different markup

            safe_name = target.product_name[:20].replace(" ", "_")
            await sp.take_screenshot(f"product_page_{safe_name}")
            return True

        except Exception as exc:
            log_error(f"find_and_click_product failed: {exc}")
            await sp.take_screenshot("product_click_failed")
            return False

    # ------------------------------------------------------------------
    # Step 4 — Add to cart
    # ------------------------------------------------------------------

    async def add_to_cart(self, sp: SmartPage, quantity: int = 1) -> bool:
        try:
            # Set quantity before clicking ATC (only works on detail pages with stepper)
            if quantity > 1:
                for _ in range(quantity - 1):
                    await sp.safe_click(self._sel["quantity_increment"], timeout=4)
                    if APP.demo_mode:
                        await asyncio.sleep(0.2)

            clicked = await sp.safe_click(self._sel["detail_add_to_cart"])
            if not clicked:
                log_error("Add-to-cart button not found or not clickable")
                return False

            # Wait for ATC confirmation (non-fatal if absent)
            try:
                await sp.page.wait_for_selector(
                    self._sel["atc_confirmation"], timeout=3_000
                )
            except Exception:
                pass

            # Dismiss upsell / protection-plan popup
            await sp.safe_click(self._sel["upsell_dismiss"], timeout=3)

            if APP.demo_mode:
                await asyncio.sleep(BROWSER.demo_delay_s)

            await sp.take_screenshot("added_to_cart")
            return True

        except Exception as exc:
            log_error(f"add_to_cart failed: {exc}")
            await sp.take_screenshot("add_to_cart_failed")
            return False

    # ------------------------------------------------------------------
    # Step 5 — Navigate to cart
    # ------------------------------------------------------------------

    async def go_to_cart(self, sp: SmartPage) -> bool:
        try:
            log_agent_action("Browser Agent", "Opening cart…")
            await sp.safe_click(self._sel["cart_icon"])
            await sp.page.wait_for_selector(
                self._sel["cart_items_list"], timeout=10_000
            )
            await sp.take_screenshot("cart_page")
            return True
        except Exception as exc:
            log_error(f"go_to_cart failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Step 6 — Apply coupon code
    # ------------------------------------------------------------------

    async def apply_coupon(self, sp: SmartPage, coupon_code: str) -> bool:
        log_agent_action("Browser Agent", f"Applying coupon: {coupon_code}")
        try:
            typed = await sp.safe_type(self._sel["promo_code_input"], coupon_code)
            if not typed:
                log_coupon_result(coupon_code, success=False)
                return False

            await sp.safe_click(self._sel["promo_code_apply"])
            await asyncio.sleep(2)

            success_text = await sp.wait_and_extract(
                self._sel["promo_success_badge"], timeout=3
            )
            error_text = await sp.wait_and_extract(
                self._sel["promo_error_message"], timeout=2
            )

            success = success_text is not None and error_text is None
            log_coupon_result(coupon_code, success=success)
            await sp.take_screenshot(f"coupon_{coupon_code}")
            return success

        except Exception as exc:
            log_error(f"apply_coupon({coupon_code}) failed: {exc}")
            log_coupon_result(coupon_code, success=False)
            return False

    # ------------------------------------------------------------------
    # Step 7 — Scrape cart totals
    # ------------------------------------------------------------------

    async def scrape_cart(self, sp: SmartPage) -> dict:
        subtotal_text = await sp.wait_and_extract(
            self._sel["cart_subtotal"], timeout=5
        )
        total_text = await sp.wait_and_extract(
            self._sel["cart_total"], timeout=5
        )
        return {
            "subtotal": _parse_price(subtotal_text) or 0.0,
            "total": _parse_price(total_text) or 0.0,
        }

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def execute_purchase(
        self,
        sp: SmartPage,
        products: list[SelectedProduct],
        coupons: list[Coupon],
    ) -> Cart:
        cart_items: list[CartItem] = []
        coupons_attempted: list[Coupon] = []
        coupons_succeeded: list[Coupon] = []

        # 1. Navigate to store
        log_agent_thinking(
            "Browser Agent",
            f"Starting purchase execution — {len(products)} product(s), "
            f"{len(coupons)} coupon(s) to try",
        )
        store_ok = await self.navigate_to_store(sp)
        if not store_ok:
            log_error("Could not load store — aborting purchase")
            return Cart()

        # 2. Add each product
        for i, product in enumerate(products):
            try:
                log_agent_action(
                    "Browser Agent",
                    f"[{i + 1}/{len(products)}] {product.product_name[:55]}",
                )

                if not await self.search_product(sp, product.product_name):
                    log_error(f"Skipping '{product.product_name}' — search failed")
                    continue

                if not await self.find_and_click_product(sp, product):
                    log_error(f"Skipping '{product.product_name}' — product not found")
                    continue

                if not await self.add_to_cart(sp, product.recommended_quantity):
                    log_error(f"Skipping '{product.product_name}' — add-to-cart failed")
                    continue

                cart_items.append(
                    CartItem(
                        product=product,
                        quantity_added=product.recommended_quantity,
                        line_total=product.effective_total,
                    )
                )
                log_agent_action(
                    "Browser Agent",
                    f"Added {product.product_name[:45]} × {product.recommended_quantity}",
                )

            except Exception as exc:
                log_error(
                    f"Unexpected error on '{product.product_name}': {exc}"
                )
                self._logger.exception(exc)
                continue  # always continue to next product

        # 3. Go to cart (only if we added something)
        if cart_items:
            await self.go_to_cart(sp)

        # 4. Apply coupons
        for coupon in coupons:
            coupons_attempted.append(coupon)
            try:
                if await self.apply_coupon(sp, coupon.coupon_code):
                    coupons_succeeded.append(coupon)
            except Exception as exc:
                log_error(f"Coupon {coupon.coupon_code} error: {exc}")

        # 5. Scrape live cart totals
        cart_data = await self.scrape_cart(sp)
        computed_subtotal = sum(item.line_total for item in cart_items)

        return Cart(
            items=cart_items,
            subtotal=cart_data["subtotal"] or computed_subtotal,
            estimated_total=cart_data["total"] or computed_subtotal,
            coupons_attempted=coupons_attempted,
            coupons_succeeded=coupons_succeeded,
        )


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"\$?\s*(\d+(?:[.,]\d+)*(?:\.\d{2})?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None
