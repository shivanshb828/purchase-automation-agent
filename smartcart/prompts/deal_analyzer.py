"""
LLM prompt template for analyzing on-page deal badges (BOGO, buy-2-get-1, rollback,
clearance) to calculate effective per-unit price and recommended stocking quantity.
"""

SYSTEM_PROMPT = """\
You are analyzing promotional text and deal badges from a retail store page to \
determine the exact deal terms and calculate real savings.

For the deal text provided, extract:
- deal_type: one of "bogo", "buy_x_get_y", "percent_off", "dollar_off", \
"rollback", "clearance", "free_shipping", "unknown"
- quantity_required: how many units the customer must buy to activate the deal (integer)
- free_quantity: number of free units received (integer, 0 if not applicable)
- discount_amount: dollar or percentage discount per transaction (string, e.g. "20%", "$3.00", or null)
- effective_unit_price: the per-unit cost after applying the deal (float)
- effective_total_for_deal: total cost to capture the full deal (float)
- estimated_savings: dollar amount saved vs paying full price for quantity_required units (float)
- human_summary: one short sentence describing the deal in plain English

Respond ONLY with a valid JSON object. No markdown, no preamble, no explanation.

Example 1:
Product: "Softsoap Hand Soap 11 oz", base_price: 3.49, deal_text: "Buy 2 Get 1 Free"
Output:
{
  "deal_type": "buy_x_get_y",
  "quantity_required": 3,
  "free_quantity": 1,
  "discount_amount": null,
  "effective_unit_price": 2.33,
  "effective_total_for_deal": 6.98,
  "estimated_savings": 3.49,
  "human_summary": "Buy 2 bottles, get a third free — effective price $2.33 each."
}

Example 2:
Product: "Bounty Paper Towels 12-pack", base_price: 21.97, deal_text: "Save 20%"
Output:
{
  "deal_type": "percent_off",
  "quantity_required": 1,
  "free_quantity": 0,
  "discount_amount": "20%",
  "effective_unit_price": 17.58,
  "effective_total_for_deal": 17.58,
  "estimated_savings": 4.39,
  "human_summary": "20% off — pay $17.58 instead of $21.97."
}\
"""

_USER_TEMPLATE = """\
Analyze this deal and calculate the exact savings.

Product: "{product_name}"
Base price: ${base_price:.2f}
Deal text: "{deal_text}"

Respond ONLY with a valid JSON object.\
"""


def build_deal_analyzer_messages(
    deal_text: str,
    product_name: str,
    base_price: float,
) -> tuple[str, str]:
    """Return (system_prompt, user_message) ready to pass to call_claude()."""
    return SYSTEM_PROMPT, _USER_TEMPLATE.format(
        product_name=product_name,
        base_price=base_price,
        deal_text=deal_text,
    )
