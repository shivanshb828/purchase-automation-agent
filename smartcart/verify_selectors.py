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
from fake_useragent import UserAgent
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

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
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-infobars",
            ],
        )
        session_path = Path("auth/walmart_session.json")
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=UserAgent().random,
            storage_state=str(session_path) if session_path.exists() else None,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "DNT": "1",
                "Connection": "keep-alive",
            },
        )
        if session_path.exists():
            print(f"   🍪  Loaded saved session from {session_path}")
        page = await ctx.new_page()
        await Stealth(
            navigator_platform_override="MacIntel",
            navigator_languages_override=("en-US", "en"),
            webgl_vendor_override="Intel Inc.",
            webgl_renderer_override="Intel Iris OpenGL Engine",
        ).apply_stealth_async(page)
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });"
        )
        page.set_default_timeout(12_000)

        # ── Step 1: Homepage ─────────────────────────────────────────────────
        section("Step 1: Homepage")
        await page.goto("https://www.walmart.com", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await dismiss_popups(page)
        await asyncio.sleep(1)
        await screenshot(page, "01_homepage")

        # Probe cart icon with multiple candidates; save winner back into results
        cart_icon_sel, _ = await probe(page, "cart_icon", [
            '[data-testid="header-cart-btn"]',
            'a[href="/cart"]',
            '[aria-label*="cart" i]',
            '[data-automation-id="header-cart-icon"]',
        ])
        results["cart_icon"] = cart_icon_sel is not None

        for name, sel in [
            ("search_bar",    'input[name="q"]'),
            ("search_button", 'button[aria-label="Search"]'),
        ]:
            found, cnt = await check(page, name, sel)
            results[name] = found
            ok(name, cnt) if found else fail(name)

        ok("cart_icon", 1) if results["cart_icon"] else fail("cart_icon")

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

            # Ratings often use aria-label — check ALL cards, not just first
            rating_sel = await probe_within("product_rating", [
                '[data-testid="product-ratings"] span[aria-label]',
                'span[aria-label*="stars"]',
                'span[aria-label*="out of 5"]',
                '[data-testid="ratings"] span[aria-label]',
                '[class*="rating"] span[aria-label]',
            ])
            if not rating_sel:
                # Search across ALL cards via page-level probe
                for candidate in ('span[aria-label*="stars"]', 'span[aria-label*="out of 5"]',
                                  '[class*="rating-stars"] span', '[data-testid*="rating"]'):
                    try:
                        cnt = await page.locator(f'[data-item-id] {candidate}').count()
                        if cnt:
                            lbl = await page.locator(f'[data-item-id] {candidate}').first.get_attribute("aria-label")
                            print(f"   🔍  product_rating (all-cards)       winner: {candidate!r}  aria-label={lbl!r}")
                            rating_sel = candidate
                            break
                    except Exception:
                        pass
            results["product_rating"] = rating_sel is not None

            review_sel = await probe_within("product_review_count", [
                '[data-testid="product-reviews"]',   # confirmed 2026-06 (data-value attr)
                '[data-testid="product-ratings"] span.f7',
                '[class*="rating-count"]',
            ])
            results["product_review_count"] = review_sel is not None

            deal_sel = await probe_within("product_deal_badge", [
                '[data-testid="badgeTagComponent"]',  # confirmed 2026-06
                '[data-automation-id="deal-badge"]',
                '[data-testid="promo-badge"]',
                'span[class*="badge"]',
            ])
            if not deal_sel:
                # Check ALL cards — not every product has a badge
                for candidate in ('[data-testid="badgeTagComponent"]', '[data-testid="promo-badge"]',
                                  'span[class*="badge"]'):
                    try:
                        cnt = await page.locator(f'[data-item-id] {candidate}').count()
                        if cnt:
                            txt = await page.locator(f'[data-item-id] {candidate}').first.inner_text(timeout=1_500)
                            print(f"   🔍  product_deal_badge (all-cards)   winner: {candidate!r}  text={txt.strip()[:30]!r}")
                            deal_sel = candidate
                            break
                    except Exception:
                        pass
            results["product_deal_badge"] = deal_sel is not None

            # Product link: use link-identifier attribute (item ID) → build /ip/{id} URL
            # This avoids click-tracking redirect URLs that trigger PerimeterX
            ip_url = None
            item_id = await first_card.locator('a[link-identifier]').first.get_attribute(
                "link-identifier", timeout=2_000
            ) if await first_card.locator('a[link-identifier]').count() else None
            if item_id:
                ip_url = f"https://www.walmart.com/ip/{item_id}"
                print(f"   🔍  {'product_link':<30} winner: 'a[link-identifier]'  item_id={item_id!r}  url={ip_url!r}")
                results["product_link"] = True
            else:
                fail("product_link")
                results["product_link"] = False

            # Also dump first card HTML for offline analysis
            try:
                card_html = await first_card.inner_html(timeout=5_000)
                Path("screenshots/card_html.html").write_text(card_html)
                print(f"   💾  Card HTML → screenshots/card_html.html ({len(card_html)} chars)")
            except Exception:
                pass

        # ── Step 3: Product detail page (try, but PerimeterX often blocks) ────
        section("Step 3: Product detail page (best effort)")
        product_url = ip_url if "ip_url" in dir() else None
        detail_ok = False

        if product_url:
            print(f"   ↗   Navigating to: {product_url[:80]}")
            await page.goto(product_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await dismiss_popups(page)
            if await is_blocked(page):
                print("   ⛔  PerimeterX blocked detail page — probing from search results instead")
            else:
                detail_ok = True

        await screenshot(page, "03_product_detail")

        section("  Probing detail page selectors")
        if detail_ok:
            for name, candidates in [
                ("detail_title", [
                    'h1[itemprop="name"]', 'h1[class*="ProductTitle"]',
                    '[data-automation-id="product-title"]', 'h1',
                ]),
                ("detail_add_to_cart", [
                    '[data-testid="add-to-cart-button"]',
                    'button[data-automation-id="add-to-cart"]',
                    'button:has-text("Add to cart")',
                    'button[aria-label*="Add to cart" i]',
                    '[data-testid*="add-to-cart"]',
                ]),
                ("quantity_increment", [
                    '[data-testid="quantity-increment"]',
                    'button[aria-label="Increase quantity"]',
                    'button[aria-label*="increment" i]',
                    'button[aria-label*="Increase" i]',
                    '[data-automation-id="quantity-plus"]',
                ]),
            ]:
                sel, cnt = await probe(page, name, candidates)
                results[name] = sel is not None
            # Dump data-testids for later analysis
            try:
                testids = await page.evaluate(
                    "() => [...new Set([...document.querySelectorAll('[data-testid]')]"
                    ".map(e=>e.getAttribute('data-testid')))].sort()"
                )
                Path("screenshots/detail_testids.txt").write_text("\n".join(testids))
                print(f"   💾  Detail testids → screenshots/detail_testids.txt")
            except Exception:
                pass
        else:
            print("   ⚠️   Detail page blocked — using card-level ATC to reach cart")
            # Go back to search results to use the card-level Add button
            await page.goto("https://www.walmart.com/search?q=paper+towels",
                            wait_until="domcontentloaded")
            await asyncio.sleep(4)
            await dismiss_popups(page)

        # ── Step 4: Add to cart ───────────────────────────────────────────────
        section("Step 4: Add to cart")
        added = False

        if detail_ok:
            # Try detail page ATC button
            for atc_sel in ['[data-testid="add-to-cart-button"]', 'button:has-text("Add to cart")',
                            'button[data-automation-id="add-to-cart"]']:
                try:
                    if await page.locator(atc_sel).count():
                        await page.locator(atc_sel).first.click(timeout=8_000)
                        print(f"   🛒  Clicked detail ATC via {atc_sel!r}")
                        await asyncio.sleep(3)
                        await dismiss_popups(page)
                        added = True
                        break
                except Exception as e:
                    print(f"   ⚠️   ATC click failed: {e}")
        else:
            # Use card-level "Add" button on search results — confirmed selector
            card_atc_sel = 'button[data-automation-id="add-to-cart"]'
            try:
                cnt = await page.locator(card_atc_sel).count()
                print(f"   🔍  card-level ATC buttons found: {cnt}")
                results["card_add_to_cart"] = cnt > 0
                if cnt:
                    await page.locator(card_atc_sel).first.click(timeout=8_000)
                    print(f"   🛒  Clicked card-level ATC ({cnt} available)")
                    await asyncio.sleep(3)
                    await dismiss_popups(page)
                    added = True
            except Exception as e:
                print(f"   ⚠️   Card ATC click failed: {e}")
        await screenshot(page, "04_add_to_cart")

        # ── Step 5: Cart ──────────────────────────────────────────────────────
        section("Step 5: Cart page")
        # Navigate to cart — either via icon click or direct URL
        cart_navigated = False
        if added:
            try:
                for cart_nav_sel in ('[aria-label*="cart" i]', 'a[href="/cart"]'):
                    try:
                        cnt = await page.locator(cart_nav_sel).count()
                        if cnt:
                            await page.locator(cart_nav_sel).first.click(timeout=8_000)
                            print(f"   🛒  Navigated to cart via {cart_nav_sel!r}")
                            await asyncio.sleep(3)
                            await dismiss_popups(page)
                            cart_navigated = True
                            break
                    except Exception:
                        pass
            except Exception:
                pass
            if not cart_navigated:
                # Direct URL fallback
                await page.goto("https://www.walmart.com/cart", wait_until="domcontentloaded")
                await asyncio.sleep(3)
                cart_navigated = True
                print("   🛒  Navigated to cart via direct URL")

        await screenshot(page, "05_cart")

        # Dump cart page data-testids for analysis
        if cart_navigated:
            try:
                cart_testids = await page.evaluate(
                    "() => [...new Set([...document.querySelectorAll('[data-testid]')]"
                    ".map(e=>e.getAttribute('data-testid')))].sort()"
                )
                Path("screenshots/cart_testids.txt").write_text("\n".join(cart_testids))
                print(f"   💾  Cart testids → screenshots/cart_testids.txt ({len(cart_testids)} values)")
            except Exception:
                pass

        section("  Probing cart selectors")
        for name, candidates in [
            ("cart_items_list", [
                '[data-testid="cart-items-list"]',
                '[data-automation-id="cart-items"]',
                '[data-testid="cart-item-stack"]',
                '[data-testid="cart-items"]',
                '[class*="CartList"]',
            ]),
            ("cart_subtotal", [
                '[data-testid="subtotal"]',
                '[data-automation-id="subtotal"]',
                '[data-testid="cart-summary-subtotal"]',
                'span[data-testid*="subtotal"]',
            ]),
            ("cart_total", [
                '[data-testid="cart-total"]',
                '[data-automation-id="estimated-total"]',
                '[data-testid="cart-summary-total"]',
                'span[data-testid*="total"]',
            ]),
            ("promo_code_input", [
                '#promo-code-input',
                'input[id*="promo"]',
                'input[placeholder*="promo" i]',
                'input[placeholder*="coupon" i]',
                'input[aria-label*="promo" i]',
                'input[aria-label*="coupon" i]',
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
