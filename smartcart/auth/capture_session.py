"""
Run this ONCE before the demo to capture an authenticated Walmart session.
Opens a real browser — log into walmart.com manually, browse around a bit
(visit a product page, scroll), then press Enter in the terminal.
Session cookies are saved so the automation reuses them and bypasses CAPTCHA.

Usage:
    cd smartcart && python auth/capture_session.py
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

STORAGE_PATH = Path(__file__).parent / "walmart_session.json"


async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        await page.goto("https://www.walmart.com")

        print("\n" + "=" * 60)
        print("  WALMART SESSION CAPTURE")
        print("=" * 60)
        print()
        print("  Steps:")
        print("  1. Log into your Walmart account in the browser window")
        print("  2. Browse around briefly — visit a product, scroll,")
        print("     add something to cart (builds trust signals)")
        print("  3. Come back here and press ENTER to save the session")
        print()
        print("=" * 60)

        input("\n  Press ENTER when ready to save session... ")

        STORAGE_PATH.parent.mkdir(exist_ok=True)
        await context.storage_state(path=str(STORAGE_PATH))

        import json
        state = json.loads(STORAGE_PATH.read_text())
        n_cookies = len(state.get("cookies", []))
        print(f"\n  ✅  Session saved to {STORAGE_PATH}")
        print(f"      {n_cookies} cookies captured")
        print("      The automation will now use these cookies.\n")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
