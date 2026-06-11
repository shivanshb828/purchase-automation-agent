"""
Feature 2 agent — searches the web for applicable coupon codes and promo offers
for each selected product+store combo, then ranks them by likely value.
"""

from __future__ import annotations

import json

from models.coupon import Coupon, CouponSearchResult
from models.product import SelectedProduct
from prompts.coupon_extractor import build_coupon_extractor_messages
from scrapers.coupon_scraper import CouponScraper
from utils.llm import call_claude
from utils.logger import get_logger, log_agent_action, log_agent_thinking, log_error


class CouponHunter:

    def __init__(self) -> None:
        self._scraper = CouponScraper()
        self._logger = get_logger(__name__)

    async def hunt(
        self,
        store_name: str,
        products: list[SelectedProduct],
    ) -> CouponSearchResult:
        """Full coupon discovery pipeline for a list of selected products."""
        queries_used: list[str] = []
        all_snippets: list[str] = []

        try:
            # ---- 1. Determine search scope: one store-wide + one per unique category ----
            unique_categories = list({p.product_name.split()[0]: p for p in products}.values())
            # Deduplicate categories from product list
            seen_categories: set[str] = set()
            products_to_search: list[SelectedProduct] = []
            for p in products:
                cat = getattr(p, "category", "general") if hasattr(p, "category") else "general"
                if cat not in seen_categories:
                    seen_categories.add(cat)
                    products_to_search.append(p)

            # Always do at least one store-wide search using the first product
            if not products_to_search and products:
                products_to_search = [products[0]]

            log_agent_thinking(
                "Coupon Hunter",
                f"Searching for {store_name} coupons — "
                f"{len(products_to_search)} search batch(es) across "
                f"{len(products)} product(s)…",
            )

            # ---- 2. Run searches ----
            for product in products_to_search:
                # Infer category from product name as a fallback
                category = "general"
                snippets = await self._scraper.search_coupons(
                    store_name=store_name,
                    product_name=product.product_name,
                    category=category,
                )
                all_snippets.extend(snippets)
                q = f"{product.product_name} {store_name} coupon"
                queries_used.append(q)
                log_agent_action(
                    "Coupon Hunter",
                    f'Searched: "{q}" → {len(snippets)} snippets',
                )

            if not all_snippets:
                self._logger.warning("No coupon snippets collected; skipping LLM extraction")
                return CouponSearchResult(
                    store=store_name,
                    coupons=[],
                    search_queries_used=queries_used,
                )

            # ---- 3. Send combined snippets to LLM ----
            combined_text = "\n\n".join(all_snippets)
            log_agent_thinking(
                "Coupon Hunter",
                f"Sending {len(all_snippets)} snippets to Claude for coupon extraction…",
            )
            system, user = build_coupon_extractor_messages(combined_text, store_name)
            raw = await call_claude(system, user, expect_json=True)

            # ---- 4. Parse and validate ----
            if not isinstance(raw, list):
                self._logger.warning(f"LLM returned non-list: {type(raw)}")
                return CouponSearchResult(
                    store=store_name,
                    coupons=[],
                    search_queries_used=queries_used,
                )

            coupons = [Coupon.model_validate(item) for item in raw]

            # ---- 5. Filter to likely-valid only ----
            coupons = [c for c in coupons if c.likely_valid]

            # ---- 6. Deduplicate by coupon_code (case-insensitive) ----
            seen_codes: set[str] = set()
            unique_coupons: list[Coupon] = []
            for coupon in coupons:
                key = coupon.coupon_code.upper()
                if key not in seen_codes:
                    seen_codes.add(key)
                    unique_coupons.append(coupon)

            # ---- 7. Log results ----
            if unique_coupons:
                log_agent_thinking(
                    "Coupon Hunter",
                    f"Found {len(unique_coupons)} valid coupon(s) for {store_name}:\n"
                    + "\n".join(
                        f"  • {c.coupon_code} — {c.discount_value}"
                        + (f" ({c.conditions})" if c.conditions else "")
                        for c in unique_coupons
                    ),
                )
            else:
                log_agent_action("Coupon Hunter", f"No valid coupons found for {store_name}")

            return CouponSearchResult(
                store=store_name,
                coupons=unique_coupons,
                search_queries_used=queries_used,
            )

        except Exception as exc:
            log_error(f"Coupon Hunter failed: {exc}")
            self._logger.exception(exc)
            return CouponSearchResult(
                store=store_name,
                coupons=[],
                search_queries_used=queries_used,
            )

    async def close(self) -> None:
        await self._scraper.close()
