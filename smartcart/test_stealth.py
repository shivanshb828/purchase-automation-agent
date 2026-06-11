"""
Stealth smoke test — navigates to Walmart search with session cookies if available.
Run after capture_session.py to verify CAPTCHA bypass.

Usage: cd smartcart && python test_stealth.py
"""
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from utils.browser import get_browser, get_page, dismiss_popups, STORAGE_STATE_PATH

load_dotenv()

async def main():
    session_present = STORAGE_STATE_PATH.exists()
    print(f"Session file present: {session_present} ({STORAGE_STATE_PATH})")

    async with get_browser() as browser:
        async with get_page(browser) as sp:
            print("Navigating to Walmart search...")
            await sp.goto("https://www.walmart.com/search?q=paper+towels")
            await asyncio.sleep(4)
            await dismiss_popups(sp.page)
            await asyncio.sleep(1)

            url = sp.page.url
            body = await sp.page.inner_text("body")
            is_blocked = "Robot or human" in body or "/blocked" in url

            await sp.take_screenshot("stealth_test")

            if is_blocked:
                print(f"❌  CAPTCHA / block page detected. URL: {url}")
                print("   → Run: python auth/capture_session.py to save a session")
            else:
                cnt = await sp.page.locator('[data-item-id]').count()
                print(f"✅  Products loaded: {cnt} cards — no CAPTCHA!")

if __name__ == "__main__":
    asyncio.run(main())
