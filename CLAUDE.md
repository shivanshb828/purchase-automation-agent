# SmartCart — AI Procurement Agent for Small Businesses

## What This Is
AI agent that automates recurring purchases for daycares/small businesses. Three features: intelligent product selection with deal awareness, external coupon/discount discovery, browser automation to execute purchases on Walmart.

## Tech Stack
Python 3.11+ (async), Playwright (browser automation), Anthropic Claude API (claude-sonnet-4-6), Pydantic (data models), Rich (console output)

## Commands
- Run: `cd smartcart && python main.py "I need paper towels and hand soap"`
- Test: `cd smartcart && python -m pytest tests/ -v`
- Single test: `cd smartcart && python -m pytest tests/test_product_selector.py -v`
- Install: `pip install -r smartcart/requirements.txt && playwright install chromium`

## Architecture
Sequential pipeline: User Request → Query Parser (LLM) → Store Search & Scrape (Playwright) → Product Evaluation (LLM) → Coupon Web Search (httpx) → Coupon Extraction (LLM) → Cart Execution (Playwright) → Cart Summary → User Approval

## Code Conventions
- Async by default — Playwright is async, everything touching it must be async
- All LLM calls return JSON, validated with Pydantic models. Always try/except with retry.
- All browser interactions try/except with screenshot-on-failure. Never crash.
- CSS selectors ONLY in config.py. Never hardcode elsewhere.
- Rich console for all user-facing output. Logger narrates every agent action.
- Functions do one thing. Orchestrator composes them.

## Key Behavior: Opportunistic Procurement
For consumable items (most daycare supplies), ALWAYS recommend stocking up on deals. BOGO on hand soap → buy 2. Buy-2-get-1-free on paper towels → buy 3. The business will use them eventually.

## What's Built
- Feature 1 (product_selector.py): COMPLETE — parse, scrape, evaluate, select
- Models, prompts, utils (llm, browser, logger): ALL COMPLETE
- Feature 2 (coupon_hunter.py): STUB — needs implementation
- Feature 3 (browser_agent.py): STUB — needs implementation
- Orchestrator + main.py: STUBS — need implementation
