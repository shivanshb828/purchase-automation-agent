# SmartCart

> AI procurement agent that automates recurring supply orders for small businesses.

Built at the **Build with Cursor hackathon** — a16z SF, June 2026.  
Team: Dhruva · Shivansh · Aayush

---

## What it does

You type: `"I need paper towels, hand soap, and goldfish crackers for my daycare."`

SmartCart:
1. Searches Walmart, evaluates every option on quality + price + active deals
2. Picks the best product per item — bumps quantity when BOGO/bulk deals are live
3. Hunts the web for promo codes
4. Opens a real browser, adds everything to cart, applies coupons
5. Prints a cart summary and waits for your approval before checkout

```
User Request
    │
    ▼
┌─────────────────────────────┐
│  Feature 1: Product Selector │  Claude picks best product per query
│  parse → search → evaluate  │  (quality × price × deals)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Feature 2: Coupon Hunter   │  Web search → LLM extracts valid codes
│  search → extract → rank    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Feature 3: Browser Agent   │  Playwright drives Walmart.com
│  add-to-cart → apply coupon │
└──────────────┬──────────────┘
               │
               ▼
       Cart Review & Approval
```

---

## Quick Start

```bash
# 1. Install dependencies
cd smartcart
pip install -r requirements.txt
playwright install chromium

# 2. Set environment variables
cp .env.example .env
# → edit .env and add ANTHROPIC_API_KEY

# 3. Run
python main.py

# Demo mode (skips prompt, uses preset request)
DEMO_REQUEST="paper towels, hand soap, and goldfish crackers" python main.py
```

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for full setup, troubleshooting, and demo-day runbook.

---

## Project Layout

```
smartcart/
├── main.py                  Entry point — Rich CLI, calls Orchestrator
├── config.py                All selectors, LLM config, browser config
├── agents/
│   ├── product_selector.py  Feature 1 — COMPLETE
│   ├── coupon_hunter.py     Feature 2 — in progress
│   ├── browser_agent.py     Feature 3 — in progress
│   └── orchestrator.py      Chains all three features
├── models/                  Pydantic types: Product, Coupon, Cart
├── prompts/                 Claude prompt templates (all four)
├── scrapers/                Coupon web-search scraper
└── utils/                   browser.py · llm.py · logger.py
```

---

## Key Files

| File | Purpose |
|---|---|
| [`BUILD_PLAN.md`](BUILD_PLAN.md) | Task breakdown, completion status, demo dry-run |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Component map, data flow, module contracts |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Setup, env vars, demo-day runbook |
| [`HANDOFF.md`](HANDOFF.md) | Team ownership, integration contracts |
| [`CLAUDE.md`](CLAUDE.md) | Full feature specs, prompts, technical decisions |

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Browser | Playwright (Chromium, headed) |
| LLM | Claude Sonnet (`claude-sonnet-4-6`) |
| Data models | Pydantic v2 |
| Console UI | Rich |
| Target store | Walmart.com |
