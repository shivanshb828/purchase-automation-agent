"""
Feature 1 agent — parses the user's natural language request into product queries,
scrapes store search results, and uses Claude to select the best option per query.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from playwright.async_api import Page

from config import WALMART
from models.product import ProductQuery, ScrapedProduct, SelectedProduct
from prompts.product_evaluation import build_product_eval_messages
from prompts.query_parser import build_query_parser_messages
from utils.llm import call_claude
from utils.logger import (
    get_logger,
    log_agent_action,
    log_agent_thinking,
    log_deal_found,
    log_error,
)

_MAX_RESULTS = 15


class ProductSelector:

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._sel = WALMART.selectors

    # ------------------------------------------------------------------
    # Public pipeline
    # ------------------------------------------------------------------

    async def parse_request(self, user_request: str) -> list[ProductQuery]:
        """Send user request through the query parser and return ProductQuery list."""
        log_agent_thinking(
            "Product Selector",
            f'Parsing request: "{user_request}"',
        )
        system, user = build_query_parser_messages(user_request)
        raw = await call_claude(system, user, expect_json=True)
        queries = [ProductQuery.model_validate(item) for item in raw]
        log_agent_action(
            "Product Selector",
            f"Identified {len(queries)} product(s): "
            + ", ".join(q.product_name for q in queries),
        )
        return queries

    async def search_and_scrape(
        self, query: ProductQuery, page: Page
    ) -> list[ScrapedProduct]:
        """Navigate to Walmart search results and scrape up to _MAX_RESULTS cards."""
        encoded = urllib.parse.quote_plus(query.product_name)
        search_url = WALMART.search_url_template.format(query=encoded)

        log_agent_action("Product Selector", f'Searching Walmart for "{query.product_name}"')
        await page.goto(search_url, wait_until="domcontentloaded")

        # Wait for at least one product card — generous timeout for live site
        try:
            await page.wait_for_selector(self._sel["product_card"], timeout=12_000)
        except Exception:
            self._logger.warning(f"No product cards found for '{query.product_name}'")
            return []

        cards = await page.locator(self._sel["product_card"]).all()
        cards = cards[:_MAX_RESULTS]
        log_agent_action("Product Selector", f"Found {len(cards)} results — extracting data…")

        products: list[ScrapedProduct] = []
        for card in cards:
            product = await self._extract_card(card)
            if product is not None:
                products.append(product)

        self._logger.info(f"Scraped {len(products)} valid products for '{query.product_name}'")
        return products

    async def evaluate_products(
        self, products: list[ScrapedProduct], query: ProductQuery
    ) -> SelectedProduct:
        """Ask Claude to pick the best product from the scraped list."""
        log_agent_thinking(
            "Product Selector",
            f"Evaluating {len(products)} options for '{query.product_name}' — "
            "weighing quality, price, and active deals…",
        )
        products_json = json.dumps(
            [p.model_dump() for p in products], default=str
        )
        system, user = build_product_eval_messages(products_json)
        raw = await call_claude(system, user, expect_json=True)
        selected = SelectedProduct.model_validate(raw)

        log_agent_action(
            "Product Selector",
            f"Selected: {selected.product_name[:60]} "
            f"(qty {selected.recommended_quantity}, ${selected.effective_total:.2f})",
        )
        self._logger.info(f"Reasoning: {selected.reasoning}")
        return selected

    async def select_best_product(
        self, query: ProductQuery, page: Page
    ) -> SelectedProduct | None:
        """Full flow for one query: scrape → evaluate → log deal if found."""
        try:
            products = await self.search_and_scrape(query, page)
            if not products:
                log_error(f"No results found for '{query.product_name}' — skipping")
                return None

            selected = await self.evaluate_products(products, query)

            if selected.deal_badge and selected.estimated_savings > 0:
                log_deal_found(
                    product=selected.product_name,
                    deal=selected.deal_applied or selected.deal_badge,
                    savings=f"${selected.estimated_savings:.2f}",
                )

            return selected

        except Exception as exc:
            log_error(f"Failed to select product for '{query.product_name}': {exc}")
            self._logger.exception(exc)
            return None

    async def process_request(
        self, user_request: str, page: Page
    ) -> list[SelectedProduct]:
        """End-to-end: parse request → select best product for each query."""
        queries = await self.parse_request(user_request)
        results: list[SelectedProduct] = []
        for query in queries:
            selected = await self.select_best_product(query, page)
            if selected is not None:
                results.append(selected)
        return results

    # ------------------------------------------------------------------
    # Card-level extraction helpers
    # ------------------------------------------------------------------

    async def _extract_card(self, card: Any) -> ScrapedProduct | None:
        """Extract all fields from a single search result card locator."""
        try:
            name = await self._try_text(card, self._sel["product_title"])
            if not name:
                return None

            # Price: prefer the machine-readable `content` attribute on itemprop
            price: float | None = None
            price_content = await self._try_attr(card, '[itemprop="price"]', "content")
            if price_content:
                price = _parse_float(price_content)
            if price is None:
                price_text = await self._try_text(card, self._sel["product_price"])
                if price_text:
                    price = _parse_price(price_text)
            if price is None:
                return None  # can't use a product we can't price

            unit_price_text = await self._try_text(card, self._sel["product_unit_price"])
            unit_price = _parse_price(unit_price_text) if unit_price_text else None

            # Rating: screen-reader span that follows the stars container
            rating_text = await self._try_text(card, self._sel["product_rating"])
            rating = _parse_rating(rating_text) if rating_text else None

            # Review count: data-value attribute is the clean integer, text is fallback
            review_count_attr = await self._try_attr(
                card, self._sel["product_review_count"], "data-value"
            )
            if review_count_attr:
                review_count = _parse_int(review_count_attr)
            else:
                review_text = await self._try_text(card, self._sel["product_review_count"])
                review_count = _parse_int(review_text) if review_text else None

            deal_badge = await self._try_text(card, self._sel["product_deal_badge"])

            oos = await self._try_text(card, self._sel["product_out_of_stock"])
            in_stock = oos is None

            # Product URL: extract numeric item ID from link-identifier attr and build
            # a direct /ip/{id} URL — avoids PerimeterX-triggering tracking redirects.
            item_id = await self._try_attr(card, self._sel["product_link"], "link-identifier")
            if item_id:
                product_url = f"{WALMART.base_url}/ip/{item_id}"
            else:
                product_url = WALMART.base_url

            return ScrapedProduct(
                product_name=name.strip(),
                price=price,
                unit_price=unit_price,
                rating=rating,
                review_count=review_count,
                deal_badge=deal_badge,
                in_stock=in_stock,
                product_url=product_url,
            )
        except Exception as exc:
            self._logger.debug(f"Card extraction failed: {exc}")
            return None

    @staticmethod
    async def _try_text(locator: Any, selector: str) -> str | None:
        """Return inner text of first matching child element, or None."""
        try:
            child = locator.locator(selector).first
            text = await child.inner_text(timeout=2_000)
            return text.strip() or None
        except Exception:
            return None

    @staticmethod
    async def _try_attr(locator: Any, selector: str, attr: str) -> str | None:
        """Return an attribute value of first matching child element, or None."""
        try:
            child = locator.locator(selector).first
            val = await child.get_attribute(attr, timeout=2_000)
            return val.strip() if val else None
        except Exception:
            return None


# ------------------------------------------------------------------
# Pure parsing helpers (no Playwright dependency — easy to unit test)
# ------------------------------------------------------------------

def _parse_price(text: str) -> float | None:
    """Extract first dollar amount from text like '$16.97' or 'Now $16.97 each'."""
    m = re.search(r"\$?\s*(\d{1,5}(?:[.,]\d{1,3})*(?:\.\d{2})?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_float(text: str) -> float | None:
    """Parse a plain float string like '16.97'."""
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return None


def _parse_rating(text: str) -> float | None:
    """Parse '4.7 out of 5 stars' → 4.7."""
    m = re.search(r"(\d+\.?\d*)\s*out\s*of", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+\.?\d*)", text)
    return float(m.group(1)) if m else None


def _parse_int(text: str) -> int | None:
    """Parse '3,241' or '3241 reviews' → 3241."""
    m = re.search(r"[\d,]+", text)
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None
