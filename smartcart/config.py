"""
Central configuration for SmartCart: store URLs, LLM settings, browser config, and CSS selectors.
All selectors live here so DOM changes only require updates in one place.
"""
# TODO: Verify all Walmart selectors against live site before demo

import os
from dotenv import load_dotenv

load_dotenv()

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 2048

# Browser
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "false").lower() == "true"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
DEMO_DELAY_MS = 800  # deliberate pause between actions so judges can follow
BROWSER_VIEWPORT = {"width": 1280, "height": 800}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
NAV_TIMEOUT_MS = 15_000
ACTION_TIMEOUT_MS = 10_000

# Store
TARGET_STORE = os.getenv("TARGET_STORE", "walmart")
STORE_URLS = {
    "walmart": "https://www.walmart.com",
}
MAX_SEARCH_RESULTS = 20

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Walmart DOM selectors — verify with Playwright inspector if they break
WALMART_SELECTORS = {
    "search_bar": 'input[name="q"]',
    "search_button": 'button[type="submit"]',
    "product_cards": '[data-testid="list-view"]',
    "product_title": '[data-automation-id="product-title"]',
    "product_price": '[data-automation-id="product-price"]',
    "add_to_cart_button": '[data-testid="add-to-cart-button"]',
    "cart_icon": '[data-testid="cart-icon"]',
    "promo_code_input": "#promo-code-input",
    "promo_code_apply": "#promo-code-submit",
    "cart_total": '[data-testid="cart-total"]',
    "quantity_input": 'input[data-testid="quantity-input"]',
    "quantity_increment": '[data-testid="quantity-increment"]',
}

SCREENSHOTS_DIR = "screenshots"
