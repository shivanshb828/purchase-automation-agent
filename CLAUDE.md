# CLAUDE.md — Agentic AI Recurring Purchase Automation System

## Project Overview

We are building an **agentic AI system that automates recurring purchases for small businesses** — starting with the daycare vertical. Daycares and similar small businesses regularly purchase consumable goods (food, hygiene products, cleaning supplies, paper goods, etc.) from mainstream retail stores. Our system acts as an intelligent procurement assistant that finds the best products, discovers savings, and executes purchases on behalf of the business.

This project is being built for the **Build with Cursor hackathon** at a16z SF. Build time is approximately 2 hours. The demo is 3 minutes. Everything we build must be demo-ready, visually impressive, and tell a coherent product story.

### Target Users
- Small business owners/operators (daycares, small offices, co-working spaces, salons)
- People who currently spend hours per week manually ordering supplies from Target, Walmart, Costco, Amazon, and grocery outlets
- Businesses that want to optimize procurement spending without hiring a dedicated purchasing role

### Product Vision (Full Scope — Beyond Hackathon)
The full product vision includes: multi-store price comparison, calendar-aware proactive purchasing (e.g., reading a Google Calendar event and suggesting supplies), smart reorder cadences, delivery time optimization, cross-sell recommendations, and support for multiple retail stores. **For the hackathon, we are NOT building all of this.** We are building three core features described below.

---

## Architecture Overview

### System Flow
```
User Request (e.g., "I need paper towels and hand soap for my daycare")
    │
    ▼
┌─────────────────────────────────────────────┐
│  FEATURE 1: Intelligent Product Selection   │
│  - Parse user request into product queries  │
│  - Search store for each product            │
│  - Scrape: name, price, rating, review      │
│    count, active deals/promos               │
│  - LLM evaluates all options                │
│  - Selects best product per query           │
│  - Adjusts quantity for bulk deals          │
│  - Outputs: selected products + reasoning   │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  FEATURE 2: Coupon & Discount Discovery     │
│  - For each selected product + store combo  │
│  - Web search for external coupons/promos   │
│  - Parse results for valid codes            │
│  - Check manufacturer coupons               │
│  - Output: list of applicable coupon codes  │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  FEATURE 3: Browser Automation & Execution  │
│  - Navigate to store website                │
│  - Search for selected product              │
│  - Add correct quantity to cart             │
│  - Apply any discovered coupon codes        │
│  - Present cart summary for user approval   │
│  - (Do NOT auto-complete checkout)          │
└─────────────────────────────────────────────┘
                      │
                      ▼
        Cart Review / User Approval Screen
```

### Tech Stack
- **Language:** Python 3.11+
- **Browser Automation:** Playwright (preferred) or Selenium
- **LLM Integration:** Anthropic Claude API (claude-sonnet-4-20250514) for product evaluation reasoning, query parsing, and coupon extraction
- **Web Scraping:** Playwright for on-page data; requests/httpx for external coupon searches
- **Frontend (if time permits):** Simple React UI or Streamlit dashboard for user interaction and cart review
- **Target Store for Demo:** Walmart.com (most automation-friendly, clean DOM structure, broad product catalog)

### Project Structure
```
/
├── claude.md                   # This file — project guide
├── README.md                   # Project readme for hackathon submission
├── requirements.txt            # Python dependencies
├── .env                        # API keys and config (DO NOT COMMIT)
├── main.py                     # Entry point — orchestrates the full flow
├── config.py                   # Store configs, LLM settings, constants
│
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py         # Main agent that coordinates all features
│   ├── product_selector.py     # Feature 1: Intelligent product selection
│   ├── coupon_hunter.py        # Feature 2: Coupon & discount discovery
│   └── browser_agent.py        # Feature 3: Browser automation & execution
│
├── models/
│   ├── __init__.py
│   ├── product.py              # Product data model (name, price, rating, reviews, deals)
│   ├── coupon.py               # Coupon data model (code, type, discount, expiry)
│   └── cart.py                 # Cart data model (items, quantities, total, savings)
│
├── scrapers/
│   ├── __init__.py
│   ├── walmart_scraper.py      # Walmart-specific scraping logic
│   ├── store_base.py           # Abstract base class for store scrapers
│   └── coupon_scraper.py       # External coupon site scraping
│
├── prompts/
│   ├── product_evaluation.py   # LLM prompt for product scoring/selection
│   ├── query_parser.py         # LLM prompt for parsing user requests into product queries
│   ├── coupon_extractor.py     # LLM prompt for extracting coupon info from search results
│   └── deal_analyzer.py        # LLM prompt for analyzing on-page deals (BOGO, etc.)
│
├── utils/
│   ├── __init__.py
│   ├── browser.py              # Playwright browser setup and helpers
│   ├── llm.py                  # Claude API client wrapper
│   └── logger.py               # Logging configuration
│
└── tests/
    ├── test_product_selector.py
    ├── test_coupon_hunter.py
    └── test_browser_agent.py
```

---

## Feature Specifications

### Feature 1: Intelligent Product Selection

**Purpose:** Given a product need (e.g., "paper towels"), evaluate all available options on the store and select the best one based on a multi-factor analysis.

**Input:** A natural language request from the user (e.g., "I need paper towels, hand soap, and snack crackers for my daycare").

**Step 1 — Query Parsing:**
- Send the user request to Claude to extract a structured list of individual product queries
- Each query should include: product name, category, any brand preferences, any quantity hints
- Example output: `[{"product": "paper towels", "category": "cleaning", "brand_preference": null, "consumable": true}, ...]`

**Step 2 — Store Search & Scraping:**
- For each product query, navigate to the store's search page
- Scrape the search results page to extract for each result:
  - `product_name` — full product title
  - `price` — current listed price
  - `unit_price` — price per unit/oz/count if available
  - `rating` — star rating (e.g., 4.6)
  - `review_count` — number of reviews
  - `deal_badge` — any visible promotion: "Buy 2 Get 1 Free", "BOGO", "Save 20%", "Rollback", "Clearance", "Special Buy"
  - `in_stock` — availability status
  - `product_url` — direct link to the product page
- Scrape the first 15-20 results maximum (first 1-2 pages)

**Step 3 — LLM Evaluation:**
- Send all scraped product data to Claude with the product evaluation prompt
- The prompt instructs Claude to weigh THREE dimensions:
  1. **Quality** — rating and review count (a 4.5 star product with 5,000 reviews is better than a 4.8 star product with 12 reviews)
  2. **Price** — absolute price and unit price; not always the cheapest, but reasonable value
  3. **Active Deals** — BOGO, buy-2-get-1, percentage off, clearance. For consumable items the business uses regularly, bulk deals are ALWAYS worth taking advantage of even if the item isn't immediately needed, because the business will eventually use it.
- Claude must output:
  - The selected product
  - Recommended quantity (may be higher than 1 if a deal makes it smart to stock up)
  - Clear reasoning explaining why this product was chosen over alternatives
  - Estimated savings from any deals

**Key Behavior — Opportunistic Procurement:**
For items flagged as `consumable: true` (most daycare supplies), the agent should ALWAYS recommend stocking up when there is a meaningful deal. A BOGO on hand soap means buy two even if the daycare only asked for one. A buy-2-get-1-free on paper towels means buy three. The reasoning should explain: "This item is a regular consumable for your business. The current deal saves you $X and you'll use these within Y weeks anyway."

**Edge Cases:**
- If no results are found, suggest an alternative product name or broader search
- If all products have low reviews (<3.5 stars), warn the user and present options anyway
- If a deal is only valid for a specific variant (e.g., specific size), make sure to select that variant
- If the store is out of stock on the best option, select the next best

---

### Feature 2: External Coupon & Discount Discovery

**Purpose:** Before executing the purchase, search the broader internet for additional savings not visible on the store page — promo codes, manufacturer coupons, cashback offers, newsletter signup discounts.

**Input:** A list of selected products with their store (output from Feature 1).

**Step 1 — Web Search for Coupons:**
- For each product + store combination, perform web searches:
  - `"{store name} coupon code {current month} {current year}"`
  - `"{product name} coupon {store name}"`
  - `"{store name} promo code"`
  - `"{product category} manufacturer coupon"`
- Target sources: RetailMeNot, Coupons.com, Honey, Slickdeals, store-specific coupon pages, manufacturer websites
- Collect the top 5-10 results per search

**Step 2 — LLM Extraction:**
- Send search result snippets to Claude with the coupon extraction prompt
- Claude extracts:
  - `coupon_code` — the actual code string (e.g., "SAVE20")
  - `discount_type` — percentage off, dollar amount off, free shipping, BOGO
  - `discount_value` — the specific amount (e.g., "20%", "$5 off")
  - `conditions` — minimum purchase, specific items only, new customers only, etc.
  - `likely_valid` — Claude's assessment of whether the coupon is probably still active (based on date mentions, source reliability)
  - `source_url` — where the coupon was found

**Step 3 — Coupon Ranking:**
- Filter out coupons that are likely expired or don't apply to our items
- Rank remaining coupons by discount value
- Select the best 1-3 codes to try at checkout
- Output a summary: "Found 2 potentially valid coupons for Walmart: SAVE20 (20% off cleaning supplies, from RetailMeNot) and FREESHIP (free shipping on orders over $35, from Slickdeals)"

**Important Notes:**
- This feature is the lowest priority of the three. If time is short, it can be simplified to a single web search + LLM parse with no ranking
- For the demo, even finding ONE valid coupon code is impressive
- Do NOT spend time building a coupon database or scraping coupon sites deeply — search engine results are sufficient
- Coupon codes often don't work. That's fine. The demo story is "we found and attempted to apply coupons automatically" — the attempt itself is the feature

---

### Feature 3: Browser Automation & Cart Execution

**Purpose:** Execute the purchasing decisions made by Features 1 and 2 by automating the store's website — searching, navigating, adding to cart, and applying coupons.

**Input:** A list of selected products with quantities (from Feature 1) and coupon codes to apply (from Feature 2).

**Browser Setup:**
- Use Playwright in headed mode (visible browser) for the demo — judges need to SEE the agent working
- Launch Chromium with a reasonable viewport (1280x800)
- Set a realistic user agent string
- Disable unnecessary resource loading (images can be loaded since we want visual demo, but block tracking scripts, ads)
- Set reasonable timeouts (15s for navigation, 10s for element interactions)

**Step 1 — Navigate to Store:**
- Go to walmart.com (or configured store URL)
- Handle any initial popups (location prompts, cookie banners, newsletter signups)
- Wait for page to fully load

**Step 2 — Search & Navigate (per product):**
- Enter the product name in the search bar
- Wait for search results to load
- Find the specific product selected by Feature 1 (match by product name — use fuzzy matching since titles may differ slightly from scrape to page)
- Click into the product page
- Verify it's the correct product and the deal/price is still valid

**Step 3 — Add to Cart:**
- Select the correct quantity
- Click "Add to Cart"
- Handle any upsell/addon popups (dismiss them)
- Confirm item was added (check for cart count increment or confirmation toast)
- Return to search for the next product

**Step 4 — Apply Coupons:**
- Once all items are in cart, navigate to cart/checkout
- Find the promo code / coupon code input field
- Enter each coupon code from Feature 2
- Check if the coupon was applied successfully (look for discount line item or error message)
- If a coupon fails, try the next one
- Log which coupons worked and which didn't

**Step 5 — Cart Summary & Approval:**
- Do NOT proceed to payment
- Scrape the final cart: item names, quantities, individual prices, any discounts applied, subtotal, tax (if shown), total
- Present this as a structured summary to the user
- Wait for user approval before any further action

**Walmart-Specific Selectors (Starting Points — VERIFY AND UPDATE):**
These are best guesses and MUST be verified against the live site during build:
```python
SELECTORS = {
    "search_bar": 'input[name="q"]',
    "search_button": 'button[type="submit"]',
    "product_cards": '[data-testid="list-view"]',
    "product_title": '[data-automation-id="product-title"]',
    "product_price": '[data-automation-id="product-price"]',
    "add_to_cart_button": '[data-testid="add-to-cart-button"]',
    "cart_icon": '[data-testid="cart-icon"]',
    "promo_code_input": '#promo-code-input',
    "promo_code_apply": '#promo-code-submit',
    "cart_total": '[data-testid="cart-total"]',
}
```
**WARNING:** Walmart changes their DOM frequently. These selectors are starting points. During build, use Playwright's inspector (`page.pause()`) to identify current selectors. Prefer `data-testid` and `data-automation-id` attributes when available — they're more stable than class names.

**Error Handling:**
- If a product can't be found, log the error and skip to the next item
- If add-to-cart fails, retry once, then skip with a warning
- If the site shows a CAPTCHA, pause and alert the user (for the demo, we'll handle this manually if it happens)
- If a popup or modal blocks interaction, attempt to dismiss it before retrying the action
- Always take a screenshot on failure for debugging

**Demo Considerations:**
- Run the browser in headed mode so it's visible
- Add small deliberate delays between actions (0.5-1s) so judges can follow what's happening
- Consider adding console logging that narrates what the agent is doing: "Searching for paper towels... Found 18 results... Evaluating options... Selected Bounty Select-A-Size 12-pack..."

---

## LLM Prompts

### Product Evaluation Prompt (Feature 1)
```
You are a smart procurement assistant for a small business (daycare). 
You are evaluating products to find the BEST option — not the cheapest, 
not the most expensive, but the best overall value.

Consider three factors:
1. QUALITY: Star rating and review count. A high rating with many reviews 
   is much more reliable than a high rating with few reviews.
2. PRICE: Look at both absolute price and unit price. The goal is good 
   value, not rock-bottom cheap.
3. DEALS & PROMOTIONS: Active deals are very important. This is a business 
   that reorders consumable supplies regularly. If there's a Buy 2 Get 1 
   Free deal, ALWAYS recommend stocking up because the business will 
   use the product eventually. Factor the effective per-unit price after 
   the deal into your evaluation.

Product data:
{product_data_json}

Respond in this JSON format:
{
  "selected_product": "Full product name",
  "product_url": "URL",
  "base_price": 0.00,
  "recommended_quantity": 1,
  "deal_applied": "Description of deal or null",
  "effective_total": 0.00,
  "estimated_savings": 0.00,
  "reasoning": "2-3 sentence explanation of why this product was chosen"
}
```

### Query Parser Prompt
```
You are parsing a small business owner's supply request into individual 
product search queries.

User request: "{user_request}"

Extract each distinct product they need. For each product, determine:
- product_name: what to search for on a store website
- category: broad category (cleaning, food, hygiene, office, etc.)
- consumable: true/false — is this something the business uses up and reorders regularly?
- brand_preference: specific brand mentioned, or null

Respond in JSON array format:
[
  {
    "product_name": "paper towels",
    "category": "cleaning", 
    "consumable": true,
    "brand_preference": null
  }
]
```

### Coupon Extractor Prompt
```
You are analyzing web search results to find valid coupon codes and 
discount offers for {store_name}.

Search results:
{search_snippets}

Extract any coupon codes, promo codes, or discount offers you find.
For each one, assess whether it's likely still valid based on any dates 
mentioned and the source reliability.

Respond in JSON array format:
[
  {
    "coupon_code": "SAVE20",
    "discount_type": "percentage",
    "discount_value": "20% off",
    "conditions": "Cleaning supplies only, min $25",
    "likely_valid": true,
    "source": "RetailMeNot"
  }
]

If no coupons are found, return an empty array [].
```

---

## Build Order & Time Allocation

**Total build time: ~2 hours (120 minutes)**

### Phase 1: Foundation (15 min)
- [ ] Set up project structure and install dependencies
- [ ] Configure Playwright and verify it can launch and navigate to Walmart
- [ ] Set up Claude API client wrapper
- [ ] Create data models (Product, Coupon, Cart)

### Phase 2: Feature 1 — Intelligent Product Selection (40 min)
- [ ] Build the query parser (send user request to Claude, get product list)
- [ ] Build the Walmart search scraper (search for a product, extract results with prices/ratings/deals)
- [ ] Build the product evaluation LLM call (send scraped data to Claude, get selection back)
- [ ] Test end-to-end: "paper towels" → search → scrape → evaluate → selected product
- [ ] Handle deal detection (BOGO, bulk discounts, clearance badges)

### Phase 3: Feature 3 — Browser Automation (40 min)
- [ ] Build the cart execution flow: search → find product → add to cart
- [ ] Handle popups and modals
- [ ] Handle quantity selection
- [ ] Build cart review scraper (read the final cart contents)
- [ ] Add visible logging / narration for demo purposes
- [ ] Test end-to-end: selected product → browser adds to cart → cart summary

### Phase 4: Feature 2 — Coupon Discovery (15 min)
- [ ] Build the web search coupon finder (search for coupons via web)
- [ ] Build the coupon extraction LLM call
- [ ] Integrate coupon application into the cart flow (enter code at checkout)
- [ ] Test: find a coupon → apply it in cart → verify result

### Phase 5: Integration & Demo Prep (10 min)
- [ ] Wire all three features into the orchestrator (main.py end-to-end flow)
- [ ] Run the full demo flow at least twice
- [ ] Fix any bugs or timing issues
- [ ] Add a clean startup script or UI entry point
- [ ] Prepare the demo script (what to say during the 3-minute demo)

---

## Dependencies

```
# requirements.txt
playwright>=1.40.0
anthropic>=0.40.0
httpx>=0.25.0
python-dotenv>=1.0.0
pydantic>=2.5.0
rich>=13.0.0           # For pretty console output during demo
```

**Setup Commands:**
```bash
pip install -r requirements.txt
playwright install chromium
```

---

## Environment Variables

```
# .env
ANTHROPIC_API_KEY=your_key_here
TARGET_STORE=walmart          # walmart | target | costco
HEADLESS_BROWSER=false        # false for demo (visible), true for testing
DEMO_MODE=true                # adds deliberate delays and verbose logging
LOG_LEVEL=INFO
```

---

## Demo Script (3 Minutes)

**0:00 - 0:30 — Problem Statement**
"Small businesses like daycares spend hours every week manually ordering supplies — paper towels, soap, snacks, cleaning products. They're browsing store websites, comparing prices, hunting for deals. We built an AI agent that does all of that automatically."

**0:30 - 2:00 — Live Demo**
"Watch what happens when I tell our agent: 'I need paper towels, hand soap, and goldfish crackers for my daycare.'
- First, it searches Walmart for each item and evaluates every option — not just price, but reviews and active deals.
- [Show the agent reasoning: 'I chose Bounty because it has 4.6 stars with 3,000 reviews, and there's a buy-2-get-1-free deal. Since you go through paper towels weekly, I'm grabbing 3 packs to save $12.']
- It also scours the internet for coupon codes and found a 15% off code on RetailMeNot.
- Now watch it execute — it's navigating Walmart, adding each item to cart, applying the coupon, and presenting the final cart for my approval."

**2:00 - 2:30 — Results**
"Total cart: $47.50. The agent saved $18.30 through smart deal stacking. And this runs on autopilot — set it up once, and your supplies show up every week."

**2:30 - 3:00 — Vision**
"This is one store, one order. The full product supports multiple stores with price comparison, calendar-aware ordering — your Google Calendar shows a parent event Friday, the agent automatically orders supplies — and smart reorder schedules that learn your consumption patterns."

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Primary store | Walmart | Most automation-friendly DOM, broadest product catalog, good deal/promo visibility |
| Browser framework | Playwright | Faster than Selenium, better async support, built-in wait strategies |
| LLM for reasoning | Claude Sonnet | Fast enough for real-time demo, strong at structured output and reasoning |
| Browser mode | Headed (visible) | Judges must see the agent working — this IS the demo |
| Checkout | Stop at cart review | Avoids payment complexity, and "human approval" is a better product story |
| Frontend | Streamlit or terminal | Whichever is faster to set up; the browser IS the visual demo |

---

## Coding Standards

- **Type hints everywhere** — use Pydantic models for all data structures
- **Async by default** — Playwright is async, lean into it
- **Structured LLM outputs** — always request JSON from Claude, always validate with Pydantic
- **Fail gracefully** — every browser interaction should have a try/except with screenshot-on-failure
- **Log everything** — use the `rich` library for pretty console output; the console IS part of the demo
- **Keep functions small** — each function does one thing; the orchestrator composes them
- **No hardcoded selectors** — put all CSS selectors in config.py so they're easy to update when Walmart changes their DOM
- **Screenshots for debugging** — take a screenshot after every major browser action during development

---

## Known Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Walmart CAPTCHA blocks automation | Medium | Use realistic browser fingerprint, add human-like delays, have a backup demo recording |
| DOM selectors break | High | Verify all selectors during setup at the event; keep selector config centralized |
| LLM returns malformed JSON | Medium | Always wrap in try/except, have fallback parsing, validate with Pydantic |
| Coupon codes don't work | High | This is fine — the demo story is "we searched and attempted"; frame it as "coupon was expired" |
| Network issues at venue | Low-Medium | Have an offline fallback: pre-recorded demo video on your phone |
| Time runs out before Feature 2 | Medium | Feature 2 (coupons) is lowest priority; demo is strong with just Features 1 + 3 |

---

## Post-Hackathon Roadmap (For Pitch, Not For Build)

These are features to mention during the demo's "Vision" section:
- Multi-store support (Target, Costco, Amazon) with cross-store price comparison
- Google Calendar integration for event-aware proactive purchasing
- Smart reorder schedules that learn consumption patterns
- Delivery time optimization (order from whichever store delivers fastest)
- Budget management and spending reports
- Team/approval workflows (manager approves cart before purchase)
- Integration with accounting software (QuickBooks, etc.)