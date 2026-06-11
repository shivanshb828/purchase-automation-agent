"""
Central configuration for SmartCart.
All store URLs, CSS selectors, LLM settings, and browser settings live here.
No other module should hardcode selectors or magic strings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# LLM Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    model: str
    max_tokens: int
    temperature: float


LLM = LLMConfig(
    api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    model="claude-sonnet-4-6",
    max_tokens=2048,
    temperature=0.0,
)

# ---------------------------------------------------------------------------
# Browser Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BrowserConfig:
    headless: bool
    viewport: dict[str, int]
    user_agent: str
    nav_timeout_ms: int        # page navigation / goto
    action_timeout_ms: int     # element interactions (click, fill, etc.)
    demo_delay_s: float        # deliberate pause between actions in demo mode


BROWSER = BrowserConfig(
    headless=os.getenv("HEADLESS_BROWSER", "false").lower() == "true",
    viewport={"width": 1280, "height": 800},
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    nav_timeout_ms=15_000,
    action_timeout_ms=10_000,
    demo_delay_s=0.7,
)

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    demo_mode: bool
    log_level: str
    max_search_results: int
    screenshots_dir: str
    target_store: str


APP = AppConfig(
    demo_mode=os.getenv("DEMO_MODE", "true").lower() == "true",
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    max_search_results=20,
    screenshots_dir="screenshots",
    target_store=os.getenv("TARGET_STORE", "walmart"),
)

# ---------------------------------------------------------------------------
# Store Configuration
# ---------------------------------------------------------------------------

@dataclass
class StoreConfig:
    name: str
    base_url: str
    search_url_template: str   # use {query} as the placeholder
    selectors: dict[str, str] = field(default_factory=dict)


# WARNING: These selectors are best guesses and MUST be verified against live
# Walmart.com before the demo. Use `page.pause()` in Playwright to inspect and
# update. Prefer data-testid and data-automation-id attributes — they're more
# stable than class names. Run `playwright codegen walmart.com` to re-derive them.
_WALMART_SELECTORS: dict[str, str] = {
    # ---- Search ----
    "search_bar":             'input[name="q"]',
    "search_button":          'button[aria-label="Search"]',

    # ---- Search results page ----
    # Verified live 2026-06: item-stack is the actual container; search-result-listview not present
    "product_cards_container": '[data-testid="item-stack"]',
    # Verified live 2026-06: [data-item-id] finds all product cards (65+ on a results page)
    "product_card":           '[data-item-id]',
    # Within a card — both verified live 2026-06 with real product text
    "product_title":          '[data-automation-id="product-title"]',
    "product_price":          '[data-automation-id="product-price"]',
    # Unit price (e.g. "$0.08/sq ft") — not always present
    "product_unit_price":     '[data-automation-id="unit-price"]',
    # Rating: accessibility span after the review count span (verified 2026-06)
    # Contains text like "4.7 out of 5 Stars. 81274 reviews"
    "product_rating":         '[data-testid="product-reviews"] + span',
    # Review count — data-testid="product-reviews" with data-value attribute (verified 2026-06)
    "product_review_count":   '[data-testid="product-reviews"]',
    # Deal / promo badge e.g. "Rollback" — data-testid confirmed live 2026-06
    "product_deal_badge":     '[data-testid="badgeTagComponent"]',
    # Out-of-stock indicator — unverified
    "product_out_of_stock":   '[data-automation-id="out-of-stock-badge"]',
    # Product link: link-identifier attribute = numeric item ID. Construct /ip/{id} URL in code.
    "product_link":           'a[link-identifier]',

    # ---- Product detail page ----
    # h1 confirmed live 2026-06; add-to-cart unverified — best guess
    "detail_title":           'h1',
    "detail_price":           '[data-automation-id="product-price"] span.f3',
    "detail_add_to_cart":     '[data-testid="add-to-cart-button"]',
    # Quantity selector on the detail page — unverified
    "quantity_input":         'input[data-testid="quantity-input"]',
    "quantity_increment":     '[data-testid="quantity-increment"]',
    "quantity_decrement":     '[data-testid="quantity-decrement"]',
    # Post-add-to-cart confirmation toast / modal — unverified
    "atc_confirmation":       '[data-testid="add-to-cart-confirmation"]',
    # "Continue" or "No thanks" on the upsell/protection-plan popup — unverified
    "upsell_dismiss":         '[data-testid="upsell-cancel-button"], button[aria-label="No, thanks"]',

    # ---- Cart / Checkout ----
    # cart_icon: header-cart-btn not found live; a[href="/cart"] is the fallback
    "cart_icon":              'a[href="/cart"]',
    "cart_items_list":        '[data-testid="cart-items-list"]',
    "cart_item_name":         '[data-automation-id="cart-item-title"]',
    "cart_item_price":        '[data-automation-id="cart-item-price"]',
    "cart_item_quantity":     '[data-testid="item-quantity"]',
    "cart_subtotal":          '[data-testid="subtotal"]',
    "cart_total":             '[data-testid="cart-total"]',

    # ---- Promo / Coupon ----
    "promo_code_input":       '#promo-code-input',
    "promo_code_apply":       '#promo-code-submit',
    "promo_success_badge":    '[data-testid="promo-success"]',
    "promo_error_message":    '[data-testid="promo-error"]',

    # ---- Common popups / overlays (including PerimeterX bot challenge) ----
    "cookie_banner_accept":   '[data-testid="cookie-accept-button"]',
    "location_popup_close":   '[data-testid="postal-code-modal"] button[aria-label="Close"]',
    "modal_close_generic":    'button[aria-label="Close"], button[data-testid="close-modal"]',
}

WALMART = StoreConfig(
    name="walmart",
    base_url="https://www.walmart.com",
    search_url_template="https://www.walmart.com/search?q={query}",
    selectors=_WALMART_SELECTORS,
)

STORES: dict[str, StoreConfig] = {
    "walmart": WALMART,
}


def get_store() -> StoreConfig:
    """Return the active store config based on TARGET_STORE env var."""
    return STORES[APP.target_store]
