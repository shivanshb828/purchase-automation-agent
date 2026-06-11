"""
Playwright browser setup helpers — creates and configures the browser instance
with the correct viewport, user agent, and resource-blocking rules for demo mode.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config import APP, BROWSER, WALMART
from utils.logger import get_logger, log_agent_action

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Browser context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_browser() -> AsyncIterator[Browser]:
    """Launch Chromium and yield a configured Browser instance."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=BROWSER.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        logger.info(f"Browser launched (headless={BROWSER.headless})")
        try:
            yield browser
        finally:
            await browser.close()
            logger.info("Browser closed")


@asynccontextmanager
async def get_page(browser: Browser) -> AsyncIterator["SmartPage"]:
    """Create a browser context + page and yield a SmartPage wrapper."""
    context: BrowserContext = await browser.new_context(
        viewport=BROWSER.viewport,
        user_agent=BROWSER.user_agent,
        # Suppress the navigator.webdriver flag that sites use to detect bots
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    # Remove the webdriver property from the JS runtime
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    page = await context.new_page()
    page.set_default_navigation_timeout(BROWSER.nav_timeout_ms)
    page.set_default_timeout(BROWSER.action_timeout_ms)

    smart = SmartPage(page=page, context=context)
    try:
        yield smart
    finally:
        await context.close()


# ---------------------------------------------------------------------------
# SmartPage wrapper
# ---------------------------------------------------------------------------

@dataclass
class SmartPage:
    """Playwright Page wrapped with demo-friendly helpers."""

    page: Page
    context: BrowserContext

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def goto(self, url: str) -> None:
        logger.info(f"Navigating to {url}")
        await self.page.goto(url, wait_until="domcontentloaded")
        if APP.demo_mode:
            await asyncio.sleep(BROWSER.demo_delay_s)

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------

    async def safe_click(self, selector: str, timeout: int = 10) -> bool:
        """Wait for element, scroll into view, click. Returns True on success."""
        try:
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout * 1000)
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=timeout * 1000)
            if APP.demo_mode:
                await asyncio.sleep(0.4)
            return True
        except Exception as exc:
            logger.debug(f"safe_click({selector!r}) failed: {exc}")
            return False

    async def safe_type(self, selector: str, text: str, timeout: int = 10) -> bool:
        """Clear field, then type text with a natural character delay."""
        try:
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout * 1000)
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=timeout * 1000)
            await loc.fill("")                          # clear existing value
            await loc.press_sequentially(text, delay=60)  # 60 ms/char looks natural
            if APP.demo_mode:
                await asyncio.sleep(0.3)
            return True
        except Exception as exc:
            logger.debug(f"safe_type({selector!r}) failed: {exc}")
            return False

    async def wait_and_extract(
        self,
        selector: str,
        attribute: str | None = None,
        timeout: int = 10,
    ) -> str | None:
        """Wait for element and return its text content or a named attribute."""
        try:
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout * 1000)
            if attribute:
                return await loc.get_attribute(attribute)
            return (await loc.inner_text()).strip()
        except Exception as exc:
            logger.debug(f"wait_and_extract({selector!r}) failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    async def take_screenshot(self, name: str) -> Path:
        """Save a screenshot to screenshots/<timestamp>_<name>.png."""
        screenshots_dir = Path(APP.screenshots_dir)
        screenshots_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"{ts}_{name}.png"
        await self.page.screenshot(path=str(path), full_page=False)
        logger.info(f"Screenshot saved: {path}")
        return path


# ---------------------------------------------------------------------------
# Popup dismissal
# ---------------------------------------------------------------------------

# Ordered from most specific to most generic — stop after first success per pass.
_POPUP_SELECTORS: list[str] = [
    # Walmart cookie / privacy banner
    '[data-testid="cookie-accept-button"]',
    'button[data-automation-id="cookie-accept"]',
    # Location / ZIP code modal
    '[data-testid="postal-code-modal"] button[aria-label="Close"]',
    'button[aria-label="close zip code modal"]',
    # Newsletter / sign-up overlays
    'button[aria-label="close"]',
    'button[aria-label="Close"]',
    '[data-testid="close-modal"]',
    '[data-automation-id="close-btn"]',
    # "No thanks" / "Not now" soft prompts
    'button:has-text("No thanks")',
    'button:has-text("Not now")',
    'button:has-text("Skip")',
]


async def dismiss_popups(page: Page) -> None:
    """Silently attempt to close common Walmart overlays. Never raises."""
    for selector in _POPUP_SELECTORS:
        try:
            loc = page.locator(selector).first
            # Very short timeout — if not immediately visible, move on
            await loc.click(timeout=1_500)
            logger.debug(f"Dismissed popup via: {selector}")
            await asyncio.sleep(0.3)
        except Exception:
            pass
