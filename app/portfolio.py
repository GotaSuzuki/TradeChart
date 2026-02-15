"""Utility helpers for portfolio holdings storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

PORTFOLIO_FILE = Path("data/portfolio.json")


def load_holdings() -> List[Dict[str, object]]:
    if not PORTFOLIO_FILE.exists():
        return []
    try:
        with PORTFOLIO_FILE.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return _normalize_holdings(raw)


def save_holdings(holdings: List[Dict[str, object]]) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PORTFOLIO_FILE.open("w", encoding="utf-8") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)


def upsert_holding(*, ticker: str, shares: int) -> Dict[str, object]:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("ticker is required")
    if shares <= 0:
        raise ValueError("shares must be positive")

    holdings = load_holdings()
    for holding in holdings:
        if holding.get("ticker") == normalized_ticker:
            holding["shares"] = int(shares)
            save_holdings(holdings)
            return holding

    new_holding = {
        "id": str(uuid4()),
        "ticker": normalized_ticker,
        "shares": int(shares),
    }
    holdings.append(new_holding)
    save_holdings(holdings)
    return new_holding


def delete_holding(holding_id: str) -> None:
    holdings = [h for h in load_holdings() if h.get("id") != holding_id]
    save_holdings(holdings)


def _normalize_holdings(raw) -> List[Dict[str, object]]:
    if not isinstance(raw, list):
        return []
    normalized: List[Dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        try:
            shares = int(float(item.get("shares")))
        except (TypeError, ValueError):
            continue
        if shares <= 0:
            continue
        holding_id = str(item.get("id") or uuid4())
        normalized.append({"id": holding_id, "ticker": ticker, "shares": shares})
    return normalized
