"""RSI strategy backtest helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.market_data import compute_rsi


@dataclass
class RsiBacktestResult:
    ticker: str
    strategy_return: float
    buy_hold_return: float
    trades: int
    latest_rsi: float
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    equity_curve: pd.DataFrame


def run_rsi_backtest(
    ticker: str,
    price_df: pd.DataFrame,
    buy_rsi: float,
    sell_rsi: float,
) -> Optional[RsiBacktestResult]:
    """Run a simple long-only RSI strategy backtest on close prices."""

    if price_df is None or price_df.empty:
        return None
    if "Date" not in price_df.columns or "Close" not in price_df.columns:
        return None

    df = price_df[["Date", "Close"]].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df.dropna(subset=["Date", "Close"], inplace=True)
    if df.empty:
        return None
    df.sort_values("Date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    enriched = compute_rsi(df).dropna(subset=["RSI"]).copy()
    if len(enriched) < 2:
        return None

    cash = 1.0
    shares = 0.0
    has_position = False
    trade_count = 0
    equity_values: list[float] = []

    for row in enriched.itertuples(index=False):
        close_price = float(row.Close)
        rsi_value = float(row.RSI)

        if (not has_position) and rsi_value <= buy_rsi:
            shares = cash / close_price
            cash = 0.0
            has_position = True
            trade_count += 1
        elif has_position and rsi_value >= sell_rsi:
            cash = shares * close_price
            shares = 0.0
            has_position = False
            trade_count += 1

        equity_values.append(cash + shares * close_price)

    first_close = float(enriched.iloc[0]["Close"])
    last_close = float(enriched.iloc[-1]["Close"])
    strategy_return = equity_values[-1] - 1.0
    buy_hold_return = (last_close / first_close) - 1.0

    equity_curve = pd.DataFrame(
        {
            "Date": enriched["Date"],
            "Equity": equity_values,
        }
    )

    return RsiBacktestResult(
        ticker=ticker,
        strategy_return=strategy_return,
        buy_hold_return=buy_hold_return,
        trades=trade_count,
        latest_rsi=float(enriched.iloc[-1]["RSI"]),
        start_date=pd.to_datetime(enriched.iloc[0]["Date"]),
        end_date=pd.to_datetime(enriched.iloc[-1]["Date"]),
        equity_curve=equity_curve,
    )
