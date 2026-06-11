"""
Playwright browser setup helpers — creates and configures the browser instance
with stealth fingerprinting, realistic user agents, human-like delays, and
optional session cookie injection to reduce PerimeterX/bot-detection triggers.
"""

from __future__ import annotations

import asyncio
import json
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from fake_useragent import UserAgent
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from config import APP, BROWSER, WALMART
from utils.logger import get_logger, log_agent_action

logger = get_logger(__name__)

# Path where capture_session.py saves authenticated Walmart cookies.
STORAGE_STATE_PATH = Path("auth/walmart_session.json")

# ---------------------------------------------------------------------------
# Browser context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_browser() -> AsyncIterator[Browser]:
    """Launch Chromium with stealth flags and yield a configured Browser instance."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=BROWSER.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-infobars",
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
    """Create a stealth browser context + page and yield a SmartPage wrapper."""
    ua = UserAgent().random

    context: BrowserContext = await browser.new_context(
        viewport=BROWSER.viewport,
        user_agent=ua,
        storage_state=str(STORAGE_STATE_PATH) if STORAGE_STATE_PATH.exists() else None,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        },
    )

    page = await context.new_page()

    # Apply playwright-stealth — removes dozens of automation fingerprints
    await Stealth(
        navigator_platform_override="MacIntel",
        navigator_languages_override=("en-US", "en"),
        webgl_vendor_override="Intel Inc.",
        webgl_renderer_override="Intel Iris OpenGL Engine",
    ).apply_stealth_async(page)

    # Extra fingerprint overrides: plugins array (stealth doesn't cover this)
    await context.add_init_script(
        "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });"
    )

    page.set_default_navigation_timeout(BROWSER.nav_timeout_ms)
    page.set_default_timeout(BROWSER.action_timeout_ms)

    logger.info(f"Page created with UA: {ua[:60]}...")
    if STORAGE_STATE_PATH.exists():
        logger.info("Loaded saved Walmart session cookies")

    smart = SmartPage(page=page, context=context)
    try:
        yield smart
    finally:
        await context.close()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def load_saved_session(context: BrowserContext) -> bool:
    """Inject saved Walmart session cookies into an existing context."""
    if not STORAGE_STATE_PATH.exists():
        return False
    try:
        with open(STORAGE_STATE_PATH) as f:
            state = json.load(f)
        for cookie in state.get("cookies", []):
            await context.add_cookies([cookie])
        logger.info("Injected saved session cookies")
        return True
    except Exception as e:
        logger.warning(f"Failed to load session: {e}")
        return False


# ---------------------------------------------------------------------------
# SmartPage wrapper
# ---------------------------------------------------------------------------

@dataclass
class SmartPage:
    """Playwright Page wrapped with stealth-friendly, human-like helpers."""

    page: Page
    context: BrowserContext

    # ------------------------------------------------------------------
    # Human-like timing helpers
    # ------------------------------------------------------------------

    async def human_delay(self, min_s: float = 0.3, max_s: float = 1.2) -> None:
        """Random pause to mimic human timing between actions."""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def human_scroll(self, direction: str = "down", amount: int = 300) -> None:
        """Scroll with a small random offset to look natural."""
        offset = random.randint(-50, 50)
        delta = amount + offset if direction == "down" else -(amount + offset)
        await self.page.mouse.wheel(0, delta)
        await self.human_delay(0.2, 0.5)

    async def human_move_to(self, selector: str) -> None:
        """Move the mouse to the element with a multi-step natural curve."""
        try:
            loc = self.page.locator(selector).first
            box = await loc.bounding_box(timeout=5_000)
            if box:
                x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await self.page.mouse.move(x, y, steps=random.randint(5, 15))
                await self.human_delay(0.1, 0.3)
        except Exception:
            pass

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
        """Move to element naturally, scroll into view, then click."""
        try:
            await self.human_move_to(selector)
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout * 1000)
            await loc.scroll_into_view_if_needed()
            await self.human_delay(0.1, 0.3)
            await loc.click(timeout=timeout * 1000)
            await self.human_delay(0.3, 0.8)
            return True
        except Exception as exc:
            logger.debug(f"safe_click({selector!r}) failed: {exc}")
            return False

    async def safe_type(self, selector: str, text: str, timeout: int = 10) -> bool:
        """Click field, clear it, then type with variable human-like character delay."""
        try:
            await self.human_move_to(selector)
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout * 1000)
            await loc.click(timeout=timeout * 1000)
            await loc.fill("")
            await loc.press_sequentially(text, delay=random.randint(40, 120))
            await self.human_delay(0.2, 0.5)
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

_POPUP_SELECTORS: list[str] = [
    # Walmart cookie / privacy banner
    '[data-testid="cookie-accept-button"]',
    'button[data-automation-id="cookie-accept"]',
    'button:has-text("Accept")',
    'button:has-text("Got it")',
    # Location / ZIP code modal
    '[data-testid="postal-code-modal"] button[aria-label="Close"]',
    'button[aria-label="close zip code modal"]',
    # Sign-in prompts and generic overlays
    'button:has-text("Continue")',
    '[role="dialog"] button[aria-label="Close"]',
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
    """Silently attempt to close common Walmart overlays. Runs two rounds. Never raises."""
    for _round in range(2):
        for selector in _POPUP_SELECTORS:
            try:
                loc = page.locator(selector).first
                await loc.click(timeout=1_500)
                logger.debug(f"Dismissed popup via: {selector}")
                await asyncio.sleep(0.3)
            except Exception:
                pass
        if _round == 0:
            await asyncio.sleep(1.0)
