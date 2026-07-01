# -*- coding: utf-8 -*-
"""Manual asset-type classification for ETFs (market-cap / dividend / bond) vs stocks.

Scope (by design, per user preference): classification is **manual-only** via the
``ASSET_TYPE_OVERRIDES`` env var. There is no automatic keyword/name-based
detection for the three ETF sub-types, because such heuristics are unreliable
across markets (A/HK/US/TW) and the user only tracks a handful of ETFs.

Codes NOT listed in ``ASSET_TYPE_OVERRIDES`` keep 100% of today's behavior:
they fall back to the existing generic ``SearchService.is_index_or_etf()``
detection (-> ``market_cap_etf``) or plain ``stock``. This module is strictly
additive and does not change any existing fetch/prompt path for untagged codes.

``.env`` format (comma-separated ``CODE:type`` pairs, case-insensitive code):

    ASSET_TYPE_OVERRIDES=0050.TW:market_cap_etf,0056.TW:dividend_etf,00679B.TW:bond_etf

Valid types: ``market_cap_etf``, ``dividend_etf``, ``bond_etf``.
Malformed entries (bad type, missing code) are skipped individually and never
raise -- a typo in one entry must not break the whole list (fail-open).
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from data_provider.base import normalize_stock_code

VALID_ASSET_TYPES = ("market_cap_etf", "dividend_etf", "bond_etf")

# Simple process-local cache: re-parse only when the raw env string changes,
# so hot-reload (.env edited + process still running) still picks up updates
# without re-parsing on every single stock in the watchlist.
_cache_raw: Optional[str] = None
_cache_parsed: Dict[str, str] = {}


def _parse_overrides(raw: str) -> Dict[str, str]:
    """Parse ``CODE:type,CODE:type`` into a ``{normalized_code: asset_type}`` dict."""
    result: Dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        code, _, asset_type = item.partition(":")
        code = code.strip()
        asset_type = asset_type.strip().lower()
        if not code or asset_type not in VALID_ASSET_TYPES:
            continue
        result[normalize_stock_code(code)] = asset_type
    return result


def get_asset_type_overrides() -> Dict[str, str]:
    """Return the parsed ``ASSET_TYPE_OVERRIDES`` map (re-parsed on env change)."""
    global _cache_raw, _cache_parsed
    raw = os.getenv("ASSET_TYPE_OVERRIDES", "")
    if raw != _cache_raw:
        _cache_raw = raw
        _cache_parsed = _parse_overrides(raw)
    return _cache_parsed


def get_asset_type(stock_code: str, stock_name: str = "") -> str:
    """Resolve the final ``asset_type`` for a stock code.

    Manual override (``ASSET_TYPE_OVERRIDES``) always wins. Unlisted codes fall
    back to the existing generic ETF/index detection, so behavior for every
    code you have NOT explicitly tagged is unchanged from before this module
    existed.
    """
    code = normalize_stock_code(stock_code)
    overrides = get_asset_type_overrides()
    if code in overrides:
        return overrides[code]

    # Local import avoids a module-load-time cycle with src.search_service.
    from src.search_service import SearchService

    if SearchService.is_index_or_etf(stock_code, stock_name):
        return "market_cap_etf"
    return "stock"
