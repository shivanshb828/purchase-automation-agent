# SmartCart — Architecture

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Entry Layer                                             │
│  main.py  →  Rich CLI prompt  →  Orchestrator.run()     │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│  Agent Layer                                             │
│                                                          │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────┐  │
│  │ ProductSelector  │  │  CouponHunter   │  │Browser │  │
│  │  (Feature 1) ✅  │  │  (Feature 2) ⬜  │  │ Agent  │  │
│  │                  │  │                 │  │(F3) ⬜  │  │
│  └────────┬─────────┘  └────────┬────────┘  └───┬────┘  │
│           │                     │               │        │
└───────────┼─────────────────────┼───────────────┼────────┘
            │                     │               │
┌───────────▼─────────────────────▼───────────────▼────────┐
│  Service Layer                                             │
│                                                            │
│  utils/llm.py          utils/browser.py    scrapers/       │
│  call_claude()         SmartPage           coupon_scraper  │
│  JSON retry logic      dismiss_popups()    httpx search    │
│                        take_screenshot()                   │
└───────────┬─────────────────────┬───────────────┬─────────┘
            │                     │               │
┌───────────▼─────────────────────▼───────────────▼─────────┐
│  Data Layer                                                 │
│                                                             │
│  models/product.py     models/coupon.py    models/cart.py  │
│  ProductQuery          Coupon              CartItem         │
│  ScrapedProduct        CouponSearchResult  Cart             │
│  SelectedProduct                           CartSummary      │
└─────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────┐
│  Config Layer  (config.py)                                   │
│  LLMConfig · BrowserConfig · AppConfig · StoreConfig(WALMART)│
│  All CSS selectors in one place — update here if DOM changes │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Flow (end-to-end)

```
str (user request)
    │  build_query_parser_messages()
    ▼
call_claude() → list[ProductQuery]
    │  for each query:
    │    page.goto(search_url)
    │    _extract_card() × N
    ▼
list[ScrapedProduct]
    │  build_product_eval_messages()
    │  call_claude()
    ▼
SelectedProduct  (per query)
    │
    ├──────────────────────────────────────────────┐
    │                                              │
    ▼                                              ▼
search_for_coupons()                     browser_agent.execute_cart()
    │  httpx → DuckDuckGo HTML             │  navigate_to_store()
    │  parse snippets                       │  find_product_on_site()
    ▼                                      │  add_to_cart()
call_claude(coupon_extractor)             │  apply_coupon()
    │                                      │  scrape_cart_summary()
    ▼                                      ▼
list[Coupon]                         CartSummary
    │                                      │
    └──────────────┬───────────────────────┘
                   ▼
            CartSummary.display()  →  Rich console output
                   │
              user approval prompt
```

---

## Module Contracts

### ProductSelector
```python
# Input
user_request: str

# Key methods
parse_request(user_request) -> list[ProductQuery]
search_and_scrape(query, page) -> list[ScrapedProduct]
evaluate_products(products, query) -> SelectedProduct
process_request(user_request, page) -> list[SelectedProduct]  # full pipeline

# Status: COMPLETE ✅
```

### CouponHunter
```python
# Input
selections: list[SelectedProduct], store: str

# Key methods
find_coupons(selections, store) -> list[Coupon]

# Internal calls
coupon_scraper.search_for_coupons(product_name, store, month_year) -> list[str]
call_claude(coupon_extractor prompt) -> list[Coupon]

# Status: STUB ⬜ — see BUILD_PLAN.md Phase 3
```

### BrowserAgent
```python
# Input
selections: list[SelectedProduct], coupons: list[Coupon], browser: Browser

# Key methods
execute_cart(selections, coupons, browser) -> CartSummary

# Internal steps
navigate_to_store(smart_page)
find_product_on_site(smart_page, selected) -> bool
add_to_cart(smart_page, selected) -> bool
apply_coupon(smart_page, coupon) -> bool
scrape_cart_summary(smart_page) -> dict

# Status: STUB ⬜ — see BUILD_PLAN.md Phase 2
```

### Orchestrator
```python
# Input
user_request: str

# Key methods
run(user_request) -> CartSummary

# Chains: ProductSelector → CouponHunter → BrowserAgent
# Uses get_browser() / get_page() context managers from utils/browser.py

# Status: STUB ⬜ — see BUILD_PLAN.md Phase 4
```

---

## External Dependencies

| Dependency | Used by | Purpose |
|---|---|---|
| Anthropic API | `utils/llm.py` | Query parsing, product evaluation, coupon extraction |
| Playwright / Chromium | `utils/browser.py`, `BrowserAgent` | Browser automation |
| DuckDuckGo HTML search | `scrapers/coupon_scraper.py` | Coupon code discovery (no API key) |
| Walmart.com | all browser interactions | Target store |

---

## Completion Status

| Component | Status | Owner |
|---|---|---|
| `config.py` | ✅ Complete | — |
| `utils/` (all three) | ✅ Complete | — |
| `models/` (all three) | ✅ Complete | — |
| `prompts/` (all four) | ✅ Complete | — |
| `agents/product_selector.py` | ✅ Complete | Dhruva |
| `scrapers/coupon_scraper.py` | ⬜ Stub | Shivanch |
| `agents/coupon_hunter.py` | ⬜ Stub | Shivanch |
| `agents/browser_agent.py` | ⬜ Stub | Ayush |
| `agents/orchestrator.py` | ⬜ Stub | Dhruva |
| `main.py` | ⬜ Stub | Dhruva |

---

## Config: Selector Update Protocol

All Walmart CSS selectors live in `config.py → _WALMART_SELECTORS`.  
Walmart changes DOM frequently. Before demo:

```bash
# Verify selectors against live site
playwright codegen walmart.com
# OR add page.pause() inside any test script and inspect manually
```

Never hardcode selectors in agent files. Always reference `WALMART.selectors["key"]`.
