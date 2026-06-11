"""
Selector verification script — runs against live Walmart.com and reports
which CSS selectors from config.py match real elements.
Run: cd smartcart && python verify_selectors.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

SCREENSHOTS = Path("screenshots")
SCREENSHOTS.mkdir(exist_ok=True)
HTML_DUMP = Path("screenshots/page_source.html")

# Popups/overlays to dismiss — CAPTCHA close button added
_POPUP_SELECTORS = [
    # Robot/human CAPTCHA — close without passing it
    'button[aria-label="close"]',
    'button[aria-label="Close"]',
    '[role="dialog"] button:has(svg)',
    # Walmart standard overlays
    '[data-testid="cookie-accept-button"]',
    'button[data-automation-id="cookie-accept"]',
    '[data-testid="postal-code-modal"] button[aria-label="Close"]',
    '[data-testid="close-modal"]',
    'button:has-text("No thanks")',
    'button:has-text("Close")',
]


async def dismiss_popups(page) -> None:
    for sel in _POPUP_SELECTORS:
        try:
            await page.locator(sel).first.click(timeout=1_500)
            await asyncio.sleep(0.4)
        except Exception:
            pass


async def is_blocked(page) -> bool:
    """Return True if Walmart is showing the PerimeterX /blocked challenge page."""
    url = page.url
    return "/blocked" in url or "px-captcha" in await page.content()


async def check_captcha_overlay(page) -> bool:
    """Return True if a CAPTCHA overlay is present (not full-page block)."""
    try:
        cnt = await page.locator("#px-captcha").count()
        return cnt > 0
    except Exception:
        return False


async def check(page, label: str, selector: str) -> tuple[bool, int]:
    try:
        count = await page.locator(selector).count()
        return count > 0, count
    except Exception:
        return False, 0


async def screenshot(page, name: str) -> None:
    path = SCREENSHOTS / f"{name}.png"
    await page.screenshot(path=str(path))
    print(f"   📸  {path}")


def ok(label, count):
    print(f"   ✅  FOUND     {label:<35} ({count} element{'s' if count != 1 else ''})")


def fail(label):
    print(f"   ❌  MISSING   {label}")


def section(title: str) -> None:
    print(f"\n── {title} {'─' * max(0, 60 - len(title))}")


# ---------------------------------------------------------------------------
# Probe helpers — try a list of candidate selectors and return first hit
# ---------------------------------------------------------------------------

async def probe(page, label: str, candidates: list[str]) -> tuple[str | None, int]:
    """Try each candidate in order; return (winning_selector, count) or (None, 0)."""
    for sel in candidates:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                print(f"   🔍  {label:<35} winner: {sel!r} ({count})")
                return sel, count
        except Exception:
            pass
    print(f"   ❌  {label:<35} no candidate matched")
    return None, 0


async def main():
    results: dict[str, bool] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await ctx.new_page()
        page.set_default_timeout(12_000)

        # ── Step 1: Homepage ─────────────────────────────────────────────────
        section("Step 1: Homepage")
        await page.goto("https://www.walmart.com", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await dismiss_popups(page)
        await asyncio.sleep(1)
        await screenshot(page, "01_homepage")

        for name, sel in [
            ("search_bar",    'input[name="q"]'),
            ("search_button", 'button[aria-label="Search"]'),
            ("cart_icon",     '[data-testid="header-cart-btn"]'),
        ]:
            found, cnt = await check(page, name, sel)
            results[name] = found
            ok(name, cnt) if found else fail(name)

        # ── Step 2: Search results (URL navigation — avoids CAPTCHA trigger) ──
        section("Step 2: Search results page (direct URL navigation)")
        await page.goto(
            "https://www.walmart.com/search?q=paper+towels",
            wait_until="domcontentloaded",
        )
        await asyncio.sleep(4)
        await dismiss_popups(page)
        await asyncio.sleep(2)

        if await is_blocked(page):
            print("   ⛔  Full PerimeterX block page detected (/blocked URL).")
            print("      This IP has been flagged. Options:")
            print("      1. Wait 10-15 min and re-run")
            print("      2. Use a different network / VPN")
            print("      3. Log into Walmart in the browser window first")
            print("      Selector verification cannot proceed — exiting.")
            await browser.close()
            return [k for k in [
                "cart_icon", "product_rating", "product_deal_badge",
                "detail_add_to_cart", "quantity_increment",
                "cart_items_list", "cart_subtotal", "cart_total", "promo_code_input",
            ]]

        if await check_captcha_overlay(page):
            print("   ⚠️   PerimeterX overlay detected (#px-captcha) — products may")
            print("        still be in DOM behind it. Continuing with selector probes...")

        # Dump HTML for offline inspection
        html = await page.content()
        HTML_DUMP.write_text(html[:80_000])
        print(f"   💾  HTML saved to {HTML_DUMP} (first 80 KB)")

        await screenshot(page, "02_search_results")

        # --- Product card container ---
        section("  Probing product card container")
        container_sel, _ = await probe(page, "product_cards_container", [
            '[data-testid="search-result-listview"]',
            '[data-testid="item-stack"]',
            '[data-testid="virtual-grid-item"]',
            '[data-testid="search-results"]',
            'section[data-automation-id="search-results"]',
            'div[class*="search-result-gridview"]',
        ])
        results["product_cards_container"] = container_sel is not None

        # --- Product card ---
        section("  Probing product cards")
        card_sel, card_count = await probe(page, "product_card", [
            '[data-item-id]',
            '[data-testid="list-view-item"]',
            '[data-testid="item-stack"]',
            '[data-testid="virtual-grid-item"]',
            'article[data-testid*="product"]',
            'div[data-testid*="item"]',
        ])
        results["product_card"] = card_sel is not None

        # --- Within-card fields (check against first card if found) ---
        if card_sel and card_count:
            section("  Probing within-card selectors")
            first_card = page.locator(card_sel).first

            async def probe_within(label, candidates):
                for sel in candidates:
                    try:
                        el = first_card.locator(sel).first
                        txt = await el.inner_text(timeout=1_500)
                        if txt.strip():
                            print(f"   🔍  {label:<30} winner: {sel!r}  text={txt.strip()[:40]!r}")
                            return sel
                    except Exception:
                        pass
                print(f"   ❌  {label:<30} no candidate matched")
                return None

            title_sel = await probe_within("product_title", [
                '[data-automation-id="product-title"]',
                '[data-testid="product-title"]',
                'span[data-automation-id="product-title"]',
                'span[class*="product-title"]',
                'a[class*="product-title"]',
                '[class*="ProductTitle"]',
            ])
            results["product_title"] = title_sel is not None

            price_sel = await probe_within("product_price", [
                '[data-automation-id="product-price"]',
                '[itemprop="price"]',
                '[data-testid="price"]',
                'div[class*="price-main"]',
                'span[class*="price-characteristic"]',
                '[class*="PriceDisplay"]',
            ])
            results["product_price"] = price_sel is not None

            rating_sel = await probe_within("product_rating", [
                '[data-testid="product-ratings"] span[aria-label]',
                'span[aria-label*="stars"]',
                'span[aria-label*="out of 5"]',
                '[data-testid="ratings"] span[aria-label]',
                '[class*="rating"] span[aria-label]',
            ])
            results["product_rating"] = rating_sel is not None

            review_sel = await probe_within("product_review_count", [
                '[data-testid="product-ratings"] span.f7',
                '[class*="rating-count"]',
                'span[class*="review-count"]',
                'span[class*="f7"]',
            ])
            results["product_review_count"] = review_sel is not None

            deal_sel = await probe_within("product_deal_badge", [
                '[data-automation-id="deal-badge"]',
                '[data-testid="promo-badge"]',
                '[data-testid="rollback-badge"]',
                'span[class*="badge"]',
                '[class*="BadgePill"]',
            ])
            results["product_deal_badge"] = deal_sel is not None

            # Product link — check attribute not text
            for link_sel in ('a[link-identifier]', 'a[href*="/ip/"]'):
                try:
                    href = await first_card.locator(link_sel).first.get_attribute("href", timeout=2_000)
                    if href:
                        print(f"   🔍  {'product_link':<30} winner: {link_sel!r}  href={href[:50]!r}")
                        results["product_link"] = True
                        break
                except Exception:
                    pass
            else:
                fail("product_link")
                results["product_link"] = False

        # ── Step 3: Product detail page ──────────────────────────────────────
        section("Step 3: Product detail page")
        # Get a real product URL from the results
        product_url = None
        for link_sel in ('a[link-identifier]', 'a[href*="/ip/"]'):
            try:
                cards = await page.locator(card_sel or '[data-item-id]').all() if card_sel else []
                if cards:
                    href = await cards[0].locator(link_sel).first.get_attribute("href", timeout=2_000)
                    if href:
                        product_url = href if href.startswith("http") else "https://www.walmart.com" + href
                        break
            except Exception:
                pass

        if product_url:
            print(f"   ↗   Navigating to: {product_url[:80]}")
            await page.goto(product_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await dismiss_popups(page)
        else:
            print("   ⚠️   No product URL found — cannot verify detail selectors")

        await screenshot(page, "03_product_detail")

        section("  Probing detail page selectors")
        for name, candidates in [
            ("detail_title", [
                'h1[itemprop="name"]',
                'h1[class*="ProductTitle"]',
                '[data-automation-id="product-title"]',
                'h1',
            ]),
            ("detail_add_to_cart", [
                '[data-testid="add-to-cart-button"]',
                'button[data-automation-id="add-to-cart"]',
                'button:has-text("Add to cart")',
                'button[aria-label*="add to cart" i]',
            ]),
            ("quantity_increment", [
                '[data-testid="quantity-increment"]',
                'button[aria-label="Increase quantity"]',
                'button[aria-label*="increment" i]',
                'button[class*="quantity-increment"]',
            ]),
        ]:
            sel, cnt = await probe(page, name, candidates)
            results[name] = sel is not None

        # ── Step 4: Add to cart ───────────────────────────────────────────────
        section("Step 4: Add to cart")
        atc_found = results.get("detail_add_to_cart", False)
        if atc_found:
            for atc_sel in [
                '[data-testid="add-to-cart-button"]',
                'button:has-text("Add to cart")',
            ]:
                try:
                    count = await page.locator(atc_sel).count()
                    if count:
                        await page.locator(atc_sel).first.click(timeout=8_000)
                        print("   🛒  Clicked Add to Cart")
                        await asyncio.sleep(3)
                        await dismiss_popups(page)
                        break
                except Exception as e:
                    print(f"   ⚠️   ATC click failed with {atc_sel!r}: {e}")
        await screenshot(page, "04_add_to_cart")

        # ── Step 5: Cart ──────────────────────────────────────────────────────
        section("Step 5: Cart page")
        cart_icon_found = results.get("cart_icon", False)
        if cart_icon_found:
            try:
                await page.locator('[data-testid="header-cart-btn"]').first.click(timeout=8_000)
                await asyncio.sleep(3)
                await dismiss_popups(page)
            except Exception as e:
                print(f"   ⚠️   Cart click failed: {e}")
        await screenshot(page, "05_cart")

        section("  Probing cart selectors")
        for name, candidates in [
            ("cart_items_list", [
                '[data-testid="cart-items-list"]',
                '[data-automation-id="cart-items"]',
                '[data-testid="cart-item-stack"]',
                '[class*="CartList"]',
            ]),
            ("cart_subtotal", [
                '[data-testid="subtotal"]',
                '[data-automation-id="subtotal"]',
                'span:has-text("Subtotal")',
            ]),
            ("cart_total", [
                '[data-testid="cart-total"]',
                '[data-automation-id="estimated-total"]',
                'span:has-text("Estimated total")',
            ]),
            ("promo_code_input", [
                '#promo-code-input',
                'input[id*="promo"]',
                'input[placeholder*="promo" i]',
                'input[placeholder*="coupon" i]',
                'input[aria-label*="promo" i]',
            ]),
        ]:
            sel, cnt = await probe(page, name, candidates)
            results[name] = sel is not None

        await browser.close()

    # ── Final report ──────────────────────────────────────────────────────────
    passed = [k for k, v in results.items() if v]
    failed_keys = [k for k, v in results.items() if not v]

    print(f"\n{'═' * 62}")
    print(f"  SELECTOR REPORT: {len(passed)} passed  /  {len(failed_keys)} failed")
    print(f"{'═' * 62}")
    if failed_keys:
        print("  ❌  Still failing:")
        for k in failed_keys:
            print(f"     • {k}")
    else:
        print("  ✅  All selectors verified!")
    print()
    return failed_keys


if __name__ == "__main__":
    failed = asyncio.run(main())
    sys.exit(0 if not failed else 1)
