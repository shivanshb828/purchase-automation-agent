# SmartCart — Deployment & Setup

## Prerequisites

- Python 3.11+
- Anthropic API key (get one at console.anthropic.com)
- Chrome/Chromium (Playwright installs it automatically)
- macOS or Linux (Windows untested)

---

## First-Time Setup

```bash
# Clone and enter the project
cd smartcart

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser
playwright install chromium

# Copy and fill in environment variables
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-...      # required
TARGET_STORE=walmart              # walmart only for now
HEADLESS_BROWSER=false            # false = visible browser (required for demo)
DEMO_MODE=true                    # adds pacing delays, verbose logging
LOG_LEVEL=INFO
DEMO_REQUEST=                     # set to skip the prompt (demo shortcut)
```

---

## Running

### Interactive mode (normal use)
```bash
cd smartcart
python main.py
# → prompts: "What supplies do you need?"
```

### Demo mode (preset request, no prompt)
```bash
DEMO_REQUEST="paper towels, hand soap, and goldfish crackers" python main.py
```

### Headless (fast testing, no visible browser)
```bash
HEADLESS_BROWSER=true DEMO_MODE=false python main.py
```

---

## Running Tests

```bash
cd smartcart
pytest tests/ -v

# Single feature
pytest tests/test_product_selector.py -v

# With live network (slower — hits real Walmart)
pytest tests/ -v --no-header -rN
```

> Tests for `coupon_hunter` and `browser_agent` are stubs until those agents are implemented.

---

## Demo-Day Runbook

**30 minutes before demo:**

1. Verify internet connection at venue
2. Run selector smoke test:
   ```bash
   cd smartcart
   python -c "
   import asyncio
   from utils.browser import get_browser, get_page, dismiss_popups
   from agents.product_selector import ProductSelector
   from models.product import ProductQuery

   async def smoke():
       async with get_browser() as b:
           async with get_page(b) as sp:
               await dismiss_popups(sp.page)
               ps = ProductSelector()
               q = ProductQuery(product_name='paper towels', category='paper_goods', consumable=True)
               results = await ps.search_and_scrape(q, sp.page)
               print(f'Scraped {len(results)} products')
               for r in results[:3]: print(r.product_name, r.price)

   asyncio.run(smoke())
   "
   ```
   Expected: prints ≥5 products with names and prices.

3. Full dry-run:
   ```bash
   DEMO_REQUEST="paper towels and hand soap" DEMO_MODE=true python main.py
   ```
   Target: completes in ≤90 seconds, no exceptions.

4. If dry-run succeeds → you're ready.  
   If Walmart shows a CAPTCHA → solve manually in the browser window and let it continue.

**Backup plan:**  
Record a GIF of a successful run before the event. Keep it on your phone.

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Claude API key |
| `TARGET_STORE` | `walmart` | Store to use (only `walmart` supported) |
| `HEADLESS_BROWSER` | `false` | `true` = no visible browser window |
| `DEMO_MODE` | `true` | Adds 0.7s delays between actions, verbose logging |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `DEMO_REQUEST` | — | Pre-set supply request; skips the interactive prompt |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ANTHROPIC_API_KEY` not set | Check `.env` and that `python-dotenv` is installed |
| `playwright install` fails | Run `pip install playwright` first, then `playwright install chromium` |
| Selector `TimeoutError` | Run selector audit — see `ARCHITECTURE.md` selector update protocol |
| CAPTCHA on Walmart | Solve manually in the browser window; script resumes automatically |
| `JSONDecodeError` from Claude | Transient — `call_claude()` retries once automatically |
| Cart page empty | Make sure add-to-cart step completed; check screenshots in `screenshots/` |
| Browser opens then closes immediately | Check `HEADLESS_BROWSER` is `false` and no exception in the log |
