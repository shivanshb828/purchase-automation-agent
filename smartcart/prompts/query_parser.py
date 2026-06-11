"""
LLM prompt template for Feature 1: parsing a natural language user request into
a structured list of individual product search queries with category and consumable flag.
"""

SYSTEM_PROMPT = """\
You are parsing a small business owner's supply request into individual product \
search queries for a retail store.

Extract each distinct product they need. For each product output:
- product_name: what to search for on a store website (concise, search-friendly)
- category: one of: cleaning, hygiene, food, paper_goods, office, laundry, kitchen, other
- consumable: true if the business uses this up and reorders regularly, false otherwise
- brand_preference: exact brand name the user mentioned, or null

Rules:
- Split combined items ("paper towels and soap") into separate objects.
- Normalise vague terms into searchable phrases ("snacks" → "goldfish crackers snack packs").
- Set brand_preference only when the user explicitly names a brand.
- Respond ONLY with a valid JSON array. No markdown, no preamble, no explanation.

Example 1:
Input: "I need paper towels, hand soap, and goldfish crackers for my daycare"
Output:
[
  {"product_name": "paper towels", "category": "paper_goods", "consumable": true, "brand_preference": null},
  {"product_name": "liquid hand soap", "category": "hygiene", "consumable": true, "brand_preference": null},
  {"product_name": "goldfish crackers", "category": "food", "consumable": true, "brand_preference": null}
]

Example 2:
Input: "Order Bounty paper towels, Lysol wipes, and some juice boxes"
Output:
[
  {"product_name": "Bounty paper towels", "category": "paper_goods", "consumable": true, "brand_preference": "Bounty"},
  {"product_name": "Lysol disinfecting wipes", "category": "cleaning", "consumable": true, "brand_preference": "Lysol"},
  {"product_name": "juice boxes", "category": "food", "consumable": true, "brand_preference": null}
]\
"""

_USER_TEMPLATE = """\
Parse this supply request into individual product search queries.

User request: "{user_request}"

Respond ONLY with a valid JSON array of product query objects.\
"""


def build_query_parser_messages(user_request: str) -> tuple[str, str]:
    """Return (system_prompt, user_message) ready to pass to call_claude()."""
    return SYSTEM_PROMPT, _USER_TEMPLATE.format(user_request=user_request)
