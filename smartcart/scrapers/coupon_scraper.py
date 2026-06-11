"""
External coupon scraper — performs web searches for store and product-specific
coupon codes, returning raw snippets for the LLM coupon extractor to parse.
"""

from __future__ import annotations

import re
from datetime import datetime

import httpx

from utils.logger import get_logger

_DDG_URL = "https://lite.duckduckgo.com/lite"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Returned when all searches fail so the LLM pipeline still gets valid input
_FALLBACK_SNIPPETS = [
    "No coupon results found. Check the store website directly for current promotions.",
]


class CouponScraper:

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._client = httpx.AsyncClient(
            headers=_HEADERS,
            timeout=10.0,
            follow_redirects=True,
        )

    async def search_coupons(
        self,
        store_name: str,
        product_name: str,
        category: str,
    ) -> list[str]:
        """Run 2-3 searches and return a flat list of raw text snippets."""
        now = datetime.now()
        month_year = now.strftime("%B %Y")  # e.g. "June 2026"

        queries = [
            f"{store_name} coupon code promo {month_year}",
            f"{product_name} {store_name} coupon discount",
            f"{store_name} {category} deals promo code",
        ]

        snippets: list[str] = []
        for query in queries:
            results = await self._search(query)
            self._logger.debug(f"Query {query!r} → {len(results)} snippets")
            snippets.extend(results)

        if not snippets:
            self._logger.warning("All coupon searches returned nothing; using fallback")
            return _FALLBACK_SNIPPETS

        return snippets

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _search(self, query: str) -> list[str]:
        """POST one query to DuckDuckGo lite and return extracted text snippets."""
        try:
            response = await self._client.post(
                _DDG_URL,
                data={"q": query, "kl": "us-en"},
            )
            if response.status_code != 200:
                self._logger.warning(
                    f"DDG returned HTTP {response.status_code} for {query!r}"
                )
                return []
            return _parse_ddg_html(response.text)
        except Exception as exc:
            self._logger.warning(f"Search request failed for {query!r}: {exc}")
            return []


# ------------------------------------------------------------------
# HTML parsing helpers (no external dependencies)
# ------------------------------------------------------------------

def _parse_ddg_html(html: str) -> list[str]:
    """Extract title + snippet pairs from DuckDuckGo lite HTML response."""
    # DDG lite results: titles in <a class="result-link">, snippets in
    # <td class="result-snippet">. Pair them up by position.
    raw_titles = re.findall(
        r'class=["\']result-link["\'][^>]*>(.*?)</a>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    raw_snippets = re.findall(
        r'class=["\']result-snippet["\'][^>]*>(.*?)</td>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    # Also try bare <td> content as a fallback (DDG sometimes varies its markup)
    if not raw_snippets:
        raw_snippets = re.findall(
            r"<td[^>]*>\s*([^<]{30,}?)\s*</td>",
            html,
            re.DOTALL | re.IGNORECASE,
        )

    combined: list[str] = []
    n = max(len(raw_titles), len(raw_snippets))
    for i in range(n):
        title = _clean(raw_titles[i]) if i < len(raw_titles) else ""
        snippet = _clean(raw_snippets[i]) if i < len(raw_snippets) else ""
        text = f"{title}\n{snippet}".strip()
        if text:
            combined.append(text)

    return combined


def _clean(fragment: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    for entity, char in [
        ("&amp;", "&"), ("&quot;", '"'), ("&#x27;", "'"),
        ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " "),
    ]:
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()
