# SmartCart — BUILD_PLAN.md

**Project:** AI-powered recurring purchase automation for daycares  
**Demo target:** 3-minute live demo at a16z SF (Build with Cursor hackathon)  
**Total build budget:** ~2 hours  
**Last updated:** 2026-06-11

---

## Current State

| Layer | File | Status |
|---|---|---|
| Config | `config.py` | ✅ Complete — all selectors, LLM, browser config |
| Utils | `utils/llm.py` | ✅ Complete — Claude client, JSON retry, code-fence strip |
| Utils | `utils/logger.py` | ✅ Complete — Rich console logger, demo narration |
| Utils | `utils/browser.py` | ✅ Complete — SmartPage, popup dismissal, screenshots |
| Models | `models/product.py` | ✅ Complete — ProductQuery, ScrapedProduct, SelectedProduct |
| Models | `models/coupon.py` | ✅ Complete — Coupon, CouponSearchResult |
| Models | `models/cart.py` | ✅ Complete — CartItem, Cart, CartSummary with Rich display |
| Prompts | `prompts/product_evaluation.py` | ✅ Complete — full prompt + examples |
| Prompts | `prompts/query_parser.py` | ✅ Complete |
| Prompts | `prompts/coupon_extractor.py` | ✅ Complete |
| Prompts | `prompts/deal_analyzer.py` | ✅ Complete |
| **Agent** | `agents/product_selector.py` | ✅ **Feature 1 fully implemented** |
| Scraper | `scrapers/store_base.py` | ⬜ Stub |
| Scraper | `scrapers/walmart_scraper.py` | ⬜ Stub (scraping done inline in product_selector) |
| Scraper | `scrapers/coupon_scraper.py` | ⬜ Stub |
| **Agent** | `agents/coupon_hunter.py` | ⬜ **Feature 2 — not started** |
| **Agent** | `agents/browser_agent.py` | ⬜ **Feature 3 — not started** |
| **Agent** | `agents/orchestrator.py` | ⬜ **Not started** |
| Entry | `main.py` | ⬜ Stub |

**Bottom line:** Foundation + Feature 1 (product selection) done. Features 2 + 3, orchestrator, and entry point remain.

---

## Priority Order

Per hackathon advisor guidance and demo impact:

```
1. Feature 3 (Browser Automation)  ← most visually impressive, highest risk
2. Feature 2 (Coupon Discovery)    ← 15-minute task, rounds out the story
3. Orchestrator + main.py          ← wires everything
4. Selector verification           ← live Walmart.com check, must happen before demo
5. Demo dry-run                    ← end-to-end smoke test with timing
```

---

## Phase 1 — Selector Verification (15 min) [BLOCKING — do first]

> **Risk:** Walmart changes DOM frequently. All downstream browser work depends on selectors in `config.py` being correct.

### Task 1.1 — Verify search + results selectors (10 min)
**Do:** Open `playwright codegen walmart.com` or `page.pause()` inside a test script.  
Navigate to `https://www.walmart.com/search?q=paper+towels`.  
Verify each selector in `config.py` under `# Search` and `# Search results page` resolves to real elements.

Key selectors to check:
```python
"product_card":        '[data-item-id]'               # each result card
"product_title":       '[data-automation-id="product-title"]'
"product_price":       '[data-automation-id="product-price"]'
"product_unit_price":  '[data-automation-id="unit-price"]'
"product_rating":      '[data-testid="product-ratings"] span[aria-label]'
"product_link":        'a[link-identifier]'
```

**Done condition:** `product_selector.py` can scrape ≥5 results for "paper towels" with name, price, and rating populated.

### Task 1.2 — Verify cart + coupon selectors (5 min)
**Do:** Navigate to `https://www.walmart.com/cart`.  
Verify:
```python
"cart_icon":           '[data-testid="header-cart-btn"]'
"cart_item_name":      '[data-automation-id="cart-item-title"]'
"cart_subtotal":       '[data-testid="subtotal"]'
"promo_code_input":    '#promo-code-input'
"promo_code_apply":    '#promo-code-submit'
```

Update `config.py` `_WALMART_SELECTORS` in place if any selector is wrong.  
**Done condition:** No `TimeoutError` when targeting cart elements on a live cart page.

---

## Phase 2 — Feature 3: Browser Agent (40 min) [SEQUENTIAL]

`agents/browser_agent.py` — drives Playwright through the full cart-building flow.

### Task 2.1 — `navigate_to_store()` (5 min)
```python
async def navigate_to_store(smart_page: SmartPage) -> None
```
- `goto(WALMART.base_url)`
- Call `dismiss_popups(smart_page.page)` from `utils/browser.py`
- Screenshot "store_landing"
- Log: `"Navigated to Walmart"`

**Risk:** Location/zip modal blocks subsequent clicks.  
**Done condition:** Function runs without exception, screenshot shows Walmart homepage.

### Task 2.2 — `find_product_on_site()` (10 min)
```python
async def find_product_on_site(
    smart_page: SmartPage,
    selected: SelectedProduct,
) -> bool
```
- Navigate to `WALMART.search_url_template.format(query=encoded_name)`
- Wait for `product_card` selector
- Scan cards for title closest to `selected.product_name` (use difflib `SequenceMatcher` ratio ≥ 0.6)
- Click matching card's `product_link` href directly (faster than clicking into the page)
- Verify detail page title contains key words from `selected.product_name`
- Screenshot "product_detail_{name}"
- Return `True` on success, `False` on mismatch/timeout

**Risk:** Walmart title on live page differs from scraped title (truncation, variant suffix).  
**Done condition:** Navigates to correct product page for "Bounty paper towels".

### Task 2.3 — `add_to_cart()` (10 min)
```python
async def add_to_cart(
    smart_page: SmartPage,
    selected: SelectedProduct,
) -> bool
```
- If `selected.recommended_quantity > 1`: use `quantity_increment` button to set quantity (click N-1 times; start at 1)
- `safe_click(WALMART.selectors["detail_add_to_cart"])`
- Wait for `atc_confirmation` toast OR cart count to increment
- Dismiss upsell modal: `safe_click(WALMART.selectors["upsell_dismiss"])` (ignore failure — modal may not appear)
- Screenshot "added_to_cart_{name}"
- Return `True` on confirmation, `False` on timeout

**Risk:** "Add to Cart" button has different selector on variant/age-restricted items.  
**Done condition:** Single item added, cart count increases by 1.

### Task 2.4 — `apply_coupon()` (5 min)
```python
async def apply_coupon(
    smart_page: SmartPage,
    coupon: Coupon,
) -> bool
```
- Navigate to cart: `safe_click(WALMART.selectors["cart_icon"])` or direct goto
- `safe_type(WALMART.selectors["promo_code_input"], coupon.coupon_code)`
- `safe_click(WALMART.selectors["promo_code_apply"])`
- Wait 2s, check for `promo_success_badge` → `True`
- Check for `promo_error_message` → `False`
- Log result either way

**Risk:** Coupon field not visible until scrolled into view; `safe_type` handles scroll.  
**Done condition:** Function returns `True` for a valid code, `False` for garbage input "FAKECODE".

### Task 2.5 — `scrape_cart_summary()` (5 min)
```python
async def scrape_cart_summary(smart_page: SmartPage) -> dict
```
- Navigate to cart page
- Extract each `cart_item_name` + `cart_item_price` + `cart_item_quantity`
- Extract `cart_subtotal` and `cart_total`
- Return raw dict (orchestrator builds `CartSummary` from it)

**Done condition:** Returns dict with ≥1 item after adding paper towels.

### Task 2.6 — `BrowserAgent.execute_cart()` (5 min)
```python
async def execute_cart(
    self,
    selections: list[SelectedProduct],
    coupons: list[Coupon],
    browser: Browser,
) -> CartSummary
```
Compose Tasks 2.1–2.5:
```
navigate_to_store()
for each selection:
    find_product_on_site()  → skip on False, log error
    add_to_cart()           → skip on False, log error
for each coupon (ranked by likely_valid):
    apply_coupon()          → try next on False
cart_dict = scrape_cart_summary()
return CartSummary built from cart_dict + selections + coupons
```

**Done condition:** Full flow runs for 2 products, `CartSummary.display()` prints without error.

---

## Phase 3 — Feature 2: Coupon Hunter (15 min) [PARALLEL-SAFE with Phase 2]

`agents/coupon_hunter.py` + `scrapers/coupon_scraper.py`

### Task 3.1 — `search_for_coupons()` in `coupon_scraper.py` (5 min)
```python
async def search_for_coupons(
    product_name: str,
    store: str,
    month_year: str,   # e.g. "June 2026"
) -> list[str]         # raw text snippets from search results
```
Use `httpx.AsyncClient` to hit DuckDuckGo HTML search (no API key needed):
```
GET https://html.duckduckgo.com/html/?q={store}+coupon+code+{month_year}
GET https://html.duckduckgo.com/html/?q={product_name}+{store}+coupon
```
Parse `<a class="result__snippet">` tags with BeautifulSoup or regex.  
Return top 10 snippet strings.  
**Done condition:** Returns ≥3 non-empty snippets for "walmart coupon code June 2026".

> **Fallback if DuckDuckGo blocks:** Use a hardcoded list of 2-3 mock coupon strings for demo. The demo story is "we found and tried" — not "we built a search engine".

### Task 3.2 — `CouponHunter.find_coupons()` in `coupon_hunter.py` (10 min)
```python
async def find_coupons(
    self,
    selections: list[SelectedProduct],
    store: str = "walmart",
) -> list[Coupon]
```
- Build search queries per product + one store-wide query
- Call `search_for_coupons()` for each, collect all snippets
- Deduplicate snippets
- Send to `call_claude()` with `prompts/coupon_extractor.py` prompt
- Parse response as `list[Coupon]` via Pydantic
- Filter `likely_valid=True`, sort by discount_value descending (rough parse: % > $ > free_ship)
- Return top 3

**Done condition:** Returns `list[Coupon]` (may be empty if none found — that's OK for demo).

---

## Phase 4 — Orchestrator (10 min) [SEQUENTIAL — after Phase 2 + 3]

`agents/orchestrator.py`

### Task 4.1 — `Orchestrator.run()` (10 min)
```python
async def run(self, user_request: str) -> CartSummary
```
```
async with get_browser() as browser:
    async with get_page(browser) as smart_page:
        # Feature 1 (already implemented)
        selections = await product_selector.process_request(user_request, smart_page.page)
        
        # Feature 2 (parallel with nothing — just await)
        coupons = await coupon_hunter.find_coupons(selections)
        
        # Feature 3
        cart_summary = await browser_agent.execute_cart(selections, coupons, browser)

return cart_summary
```

Log each phase transition with `log_agent_action`.  
**Done condition:** `Orchestrator().run("paper towels and hand soap")` runs end-to-end without unhandled exception.

---

## Phase 5 — Entry Point (5 min) [SEQUENTIAL — after Phase 4]

`main.py`

### Task 5.1 — Rich CLI entry point (5 min)
```python
async def main() -> None:
    console = Console()
    console.print(Panel("[bold cyan]SmartCart[/bold cyan] — AI Procurement Agent", ...))
    
    user_request = Prompt.ask("[bold]What supplies do you need?[/bold]")
    # or: hardcode for demo — "paper towels, hand soap, and goldfish crackers"
    
    orchestrator = Orchestrator()
    cart_summary = await orchestrator.run(user_request)
    
    console.print(cart_summary.display())
    Confirm.ask("Approve this cart and proceed to checkout?")
```

Add `DEMO_REQUEST` env var override so `main.py` skips the prompt in demo mode:
```python
user_request = os.getenv("DEMO_REQUEST") or Prompt.ask(...)
```

**Done condition:** `python main.py` (with `DEMO_REQUEST` set) runs full flow, prints cart, waits for approval.

---

## Phase 6 — Demo Dry-Run (10 min) [BLOCKING — do before presenting]

### Task 6.1 — Selector smoke test (5 min)
```bash
cd smartcart
python -c "
import asyncio
from utils.browser import get_browser, get_page, dismiss_popups
from agents.product_selector import ProductSelector

async def smoke():
    async with get_browser() as b:
        async with get_page(b) as sp:
            await dismiss_popups(sp.page)
            ps = ProductSelector()
            results = await ps.search_and_scrape(
                type('Q', (), {'product_name': 'paper towels'})(), sp.page
            )
            print(f'Scraped {len(results)} products')
            for r in results[:3]:
                print(r.product_name, r.price, r.deal_badge)

asyncio.run(smoke())
"
```
**Done condition:** Prints ≥5 products with names and prices.

### Task 6.2 — Full end-to-end dry-run (5 min)
```bash
DEMO_REQUEST="paper towels and hand soap" DEMO_MODE=true python main.py
```
Time the run. Target: under 90 seconds for 2 products.  
Fix any runtime errors. Take note of any selector mismatches.  
**Done condition:** Cart summary prints. No uncaught exceptions. Browser visible throughout.

---

## Phase 7 — Demo Hardening (if time permits)

> Only if dry-run exposed issues. Skip if clean.

### Task 7.1 — CAPTCHA fallback (5 min)
If Walmart shows a CAPTCHA:
- `take_screenshot("captcha_detected")`
- `log_error("CAPTCHA detected — manual intervention required")`
- Pause Playwright (`page.pause()`) to allow manual solve
- Resume automatically when user closes the inspector

### Task 7.2 — Pre-recorded fallback (5 min)
Record a GIF of a successful run using `mcp__claude-in-chrome__gif_creator`.  
Keep on phone as backup if live demo fails.

### Task 7.3 — Demo-mode timing audit (5 min)
Verify `BROWSER.demo_delay_s = 0.7` feels right for judges to follow.  
Increase to 1.0 if actions feel rushed, decrease to 0.4 if it's slow.

---

## Parallel Work Map

```
Time →
0:00    Task 1.1 ─── Task 1.2 ─┐
                                │
0:15    Task 2.1 ─┐             │ (selector fixes applied)
        Task 2.2 ─┤ sequential  │
        Task 2.3 ─┤             │
        Task 2.4 ─┤             │
        Task 2.5 ─┤             │
        Task 2.6 ─┘             │
                                ┤ (can overlap with Phase 2)
0:15    Task 3.1 ───────────────┘
        Task 3.2 ─┘
                                
0:55    Task 4.1  (orchestrator)
        Task 5.1  (main.py)
                                
1:10    Task 6.1  (smoke test)
        Task 6.2  (full dry-run)
        
1:20    Phase 7 (if needed)
```

**Phase 2 and Phase 3 can be built in parallel** by two developers — they share no runtime dependencies (only import from models/utils which are complete).

---

## Done Conditions by Feature

| Feature | Done When |
|---|---|
| F1 — Product Selection | Already done ✅ |
| F2 — Coupon Discovery | `find_coupons(selections)` returns `list[Coupon]` without error |
| F3 — Browser Automation | Browser visibly adds 2 items to Walmart cart, cart summary prints |
| Orchestrator | `Orchestrator().run("paper towels")` runs end-to-end |
| Entry point | `python main.py` starts, prompts, runs, displays cart, awaits approval |
| Demo-ready | Full run ≤ 90s, no exceptions, browser visible, Rich output clean |

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Walmart DOM changed — selectors fail | High | Phase 1 selector audit is blocking. Run `playwright codegen` to re-derive. |
| CAPTCHA blocks automation | High | `page.pause()` fallback; pre-recorded GIF on phone |
| LLM returns malformed JSON | Medium | `call_claude(expect_json=True)` auto-retries once with explicit instruction |
| DuckDuckGo blocks coupon search | Low | Hardcode 2 mock coupons; the demo is "we searched and tried", not "we found valid coupons" |
| ATC button selector wrong | Medium | Use `playwright codegen` on live product page during selector audit |
| Upsell modal blocks ATC confirmation | Medium | `upsell_dismiss` selector + `safe_click` with ignore-on-failure pattern |
| Run time > 90s | Low | Reduce `demo_delay_s`, parallelize product searches with `asyncio.gather` |

---

## File Completion Checklist

```
smartcart/
├── config.py                   ✅
├── main.py                     ⬜ Phase 5
├── agents/
│   ├── product_selector.py     ✅
│   ├── coupon_hunter.py        ⬜ Phase 3
│   ├── browser_agent.py        ⬜ Phase 2
│   └── orchestrator.py         ⬜ Phase 4
├── scrapers/
│   ├── store_base.py           ⬜ (low priority stub — skip if time-pressed)
│   ├── walmart_scraper.py      ⬜ (scraping already in product_selector — skip)
│   └── coupon_scraper.py       ⬜ Phase 3
├── prompts/                    ✅ all four implemented
├── models/                     ✅ all three implemented
└── utils/                      ✅ all three implemented
```

> `store_base.py` and `walmart_scraper.py` stubs are not on the critical path — `product_selector.py` does Walmart scraping inline via Playwright. Skip both unless refactoring for multi-store support (post-hackathon).

---

## Demo Script Reference

```
0:00–0:30   Problem: daycares spend hours/week manually ordering supplies
0:30–0:45   "Watch what happens when I tell our agent:"
            → type DEMO_REQUEST into terminal / UI
0:45–1:15   Feature 1 visible: Rich console shows agent searching, evaluating,
            selecting products with reasoning
1:15–1:30   Feature 2 visible: "Found 1 coupon: SAVE15 from RetailMeNot"
1:30–2:00   Feature 3 visible: browser opens Walmart, searches, adds to cart
2:00–2:15   Cart summary prints: items, quantities, coupon applied, total saved
2:15–2:30   "Total: $47.50. Saved $18.30. Cart awaits your approval."
2:30–3:00   Vision: multi-store, calendar-aware, smart reorder schedules
```
