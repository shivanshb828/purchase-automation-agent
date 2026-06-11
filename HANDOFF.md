# SmartCart — Team Handoff

**Team:** Dhruva · Shivanch · Ayush  
**Event:** Build with Cursor hackathon — a16z SF  
**Demo:** June 2026 (3-minute live demo)

---

## Ownership Map

| Component | Owner | Status | Files |
|---|---|---|---|
| Product Selector (F1) | Dhruva | ✅ Complete | `agents/product_selector.py` |
| Orchestrator + main.py | Dhruva | ⬜ TODO | `agents/orchestrator.py`, `main.py` |
| Coupon Scraper | Shivanch | ⬜ TODO | `scrapers/coupon_scraper.py` |
| Coupon Hunter (F2) | Shivanch | ⬜ TODO | `agents/coupon_hunter.py` |
| Browser Agent (F3) | Ayush | ⬜ TODO | `agents/browser_agent.py` |
| Foundation (done) | Dhruva | ✅ | `config.py`, `utils/`, `models/`, `prompts/` |

---

## Integration Contracts

These are the exact function signatures at each boundary. Do not change them without coordinating — Orchestrator depends on all three.

### F1 → Orchestrator

```python
# agents/product_selector.py — COMPLETE, do not modify signature
from agents.product_selector import ProductSelector

selector = ProductSelector()
selections: list[SelectedProduct] = await selector.process_request(
    user_request: str,
    page: Page,           # Playwright Page from utils/browser.get_page()
)
```

### F2 → Orchestrator (Shivanch to implement)

```python
# agents/coupon_hunter.py
from agents.coupon_hunter import CouponHunter

hunter = CouponHunter()
coupons: list[Coupon] = await hunter.find_coupons(
    selections: list[SelectedProduct],
    store: str = "walmart",
)
# Returns [] if no coupons found — that is valid and expected
```

### F3 → Orchestrator (Ayush to implement)

```python
# agents/browser_agent.py
from agents.browser_agent import BrowserAgent

agent = BrowserAgent()
cart_summary: CartSummary = await agent.execute_cart(
    selections: list[SelectedProduct],
    coupons: list[Coupon],
    browser: Browser,     # from utils/browser.get_browser()
)
```

### Orchestrator (Dhruva to implement)

```python
# agents/orchestrator.py
from agents.orchestrator import Orchestrator

result: CartSummary = await Orchestrator().run(user_request: str)
```

---

## Shared Infrastructure (read-only for F2/F3 builders)

These are complete and tested. Import, don't rewrite.

```python
# LLM calls
from utils.llm import call_claude
raw = await call_claude(system_prompt, user_message, expect_json=True)  # → dict

# Browser
from utils.browser import get_browser, get_page, dismiss_popups, SmartPage
async with get_browser() as browser:
    async with get_page(browser) as smart_page:
        await dismiss_popups(smart_page.page)
        await smart_page.safe_click(selector)
        await smart_page.safe_type(selector, text)
        await smart_page.take_screenshot("label")

# Logging (use these — they drive the Rich demo output)
from utils.logger import log_agent_action, log_agent_thinking, log_deal_found, log_error
log_agent_action("Browser Agent", "Adding Bounty paper towels to cart...")
log_agent_thinking("Coupon Hunter", "Searching for Walmart promo codes...")

# Config
from config import WALMART, APP, BROWSER, LLM
WALMART.selectors["detail_add_to_cart"]   # all selectors here
APP.demo_mode                              # True in demo
```

---

## Shivanch — F2 Checklist (Coupon Hunter)

```
⬜ scrapers/coupon_scraper.py
    - search_for_coupons(product_name, store, month_year) -> list[str]
    - Use httpx.AsyncClient to query DuckDuckGo HTML (no API key needed):
      GET https://html.duckduckgo.com/html/?q={store}+coupon+code+{month_year}
    - Parse <a class="result__snippet"> text nodes
    - Return top 10 snippet strings
    - Fallback: return 2 hardcoded snippets if request fails (demo safety net)

⬜ agents/coupon_hunter.py
    - CouponHunter class with find_coupons(selections, store) -> list[Coupon]
    - Call coupon_scraper.search_for_coupons() for each product + one store-wide query
    - Send combined snippets to call_claude() with prompts/coupon_extractor.py
    - Validate response as list[Coupon] via Pydantic
    - Filter likely_valid=True, return top 3
    - Return [] on any failure (never raise — coupon discovery is optional)
```

Prompt to use: `from prompts.coupon_extractor import build_coupon_extractor_messages`  
Model: `Coupon` from `models/coupon.py` — already defined, just validate against it.

---

## Ayush — F3 Checklist (Browser Agent)

```
⬜ agents/browser_agent.py
    - BrowserAgent class
    - execute_cart(selections, coupons, browser) -> CartSummary  ← main entry point

    Internal methods (implement in this order):
    ⬜ navigate_to_store(smart_page)
       → smart_page.goto(WALMART.base_url), dismiss_popups(), screenshot
    ⬜ find_product_on_site(smart_page, selected) -> bool
       → goto search URL, find card matching selected.product_name
       → use difflib.SequenceMatcher(ratio >= 0.6) for fuzzy title match
       → navigate to product page, return True/False
    ⬜ add_to_cart(smart_page, selected) -> bool
       → set quantity (click increment button N-1 times if qty > 1)
       → safe_click("detail_add_to_cart"), wait for confirmation
       → dismiss upsell modal (ignore failure), return True/False
    ⬜ apply_coupon(smart_page, coupon) -> bool
       → navigate to cart, safe_type("promo_code_input", code)
       → safe_click("promo_code_apply"), check success/error badge
    ⬜ scrape_cart_summary(smart_page) -> dict
       → extract cart item names, prices, quantities, subtotal, total
```

Key imports to use:
```python
from config import WALMART
from utils.browser import SmartPage, dismiss_popups
from utils.logger import log_agent_action, log_error
from models.product import SelectedProduct
from models.coupon import Coupon
from models.cart import Cart, CartItem, CartSummary
```

See `BUILD_PLAN.md` Phase 2 for exact function signatures and done conditions.

---

## Integration Test (run after both F2 and F3 are done)

```bash
# Dhruva runs this once orchestrator + main.py are wired
DEMO_REQUEST="paper towels and hand soap" DEMO_MODE=true python main.py
```

Expected output:
1. Rich console shows Feature 1 reasoning (product selection)
2. Shows coupon search result (or "no coupons found")
3. Browser opens, visibly adds items to Walmart cart
4. Cart summary table prints with totals
5. Approval prompt appears

---

## Git Workflow

- Branch: `tel-aviv` (current workspace branch)
- Base: `main`
- PR when all three features are complete and dry-run passes
- Keep commits small and named by feature: `feat(browser): add add_to_cart()`

Do **not** push API keys. `.env` is gitignored.
