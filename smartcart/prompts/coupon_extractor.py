"""
LLM prompt template for Feature 2: extracting structured coupon/promo data from
raw web search result snippets, including validity assessment and discount details.
"""

SYSTEM_PROMPT = """\
You are extracting coupon codes and discount offers from web search result snippets \
for a retail store. Your output will be used to automatically apply savings at checkout.

For each coupon or promo code you find, output:
- coupon_code: the exact code string to enter at checkout (e.g. "SAVE20"), or null \
if it's an automatic/clip discount with no code
- discount_type: one of "percentage", "dollar_off", "free_shipping", "bogo", "other"
- discount_value: human-readable discount (e.g. "20% off", "$5 off orders over $35")
- conditions: any restrictions — minimum order, specific categories, new customers only, etc. (or null)
- likely_valid: true if the coupon appears current (recent date mentions, active source), \
false if it looks expired or unverified
- source: name of the site where you found it (e.g. "RetailMeNot", "Honey", "Slickdeals")
- source_url: URL of the page where the coupon was found, or null if not available

Rules:
- Only include coupons that apply to the specified store.
- If the same code appears multiple times, include it once.
- If no valid coupons are found, return an empty array [].
- Respond ONLY with a valid JSON array. No markdown, no preamble, no explanation.

Example input (store: Walmart, snippets contain two codes):
---
RetailMeNot — Walmart promo codes June 2025 | Verified today
Use code WMRT15 at checkout for 15% off your entire order. Minimum purchase $50.
https://www.retailmenot.com/view/walmart.com

Slickdeals forum post 3 days ago:
"Found a working Walmart code: FREESHIP35 — free shipping on orders over $35, \
no expiry listed but worked yesterday."
---

Example output:
[
  {
    "coupon_code": "WMRT15",
    "discount_type": "percentage",
    "discount_value": "15% off",
    "conditions": "Minimum purchase $50",
    "likely_valid": true,
    "source": "RetailMeNot",
    "source_url": "https://www.retailmenot.com/view/walmart.com"
  },
  {
    "coupon_code": "FREESHIP35",
    "discount_type": "free_shipping",
    "discount_value": "Free shipping",
    "conditions": "Orders over $35",
    "likely_valid": true,
    "source": "Slickdeals",
    "source_url": null
  }
]\
"""

_USER_TEMPLATE = """\
Extract all coupon codes and discount offers for {store_name} from these search results.

Search result snippets:
---
{search_snippets}
---

Respond ONLY with a valid JSON array of coupon objects. Return [] if none found.\
"""


def build_coupon_extractor_messages(
    search_snippets: str,
    store_name: str,
) -> tuple[str, str]:
    """Return (system_prompt, user_message) ready to pass to call_claude()."""
    return SYSTEM_PROMPT, _USER_TEMPLATE.format(
        store_name=store_name,
        search_snippets=search_snippets,
    )
