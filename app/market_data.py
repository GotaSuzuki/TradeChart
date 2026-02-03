"""Utilities for downloading price history and computing technical indicators."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import requests
import yfinance as yf

from app.config import get_config


def download_price_history(ticker: str, *, period: str = "2y") -> pd.DataFrame:
    alpaca_df = _download_from_alpaca(ticker)
    if alpaca_df is not None and not alpaca_df.empty:
        return alpaca_df

    data = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()
    data.sort_values("Date", inplace=True)
    data.reset_index(drop=True, inplace=True)
    return data


def compute_rsi(price_df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    if "Close" not in price_df.columns:
        return price_df.copy()

    result = price_df.copy()
    close = result["Close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace({0: pd.NA})
    rsi = 100 - (100 / (1 + rs))
    result["RSI"] = rsi
    return result


def _download_from_alpaca(ticker: str) -> Optional[pd.DataFrame]:
    config = get_config()
    if not config.alpaca_api_key_id or not config.alpaca_api_secret_key:
        return None

    base_url = config.alpaca_data_base_url.rstrip("/")
    url = f"{base_url}/v2/stocks/{ticker}/bars"
    params = {
        "timeframe": "1Day",
        "limit": 1000,
        "feed": config.alpaca_data_feed or "iex",
        "adjustment": "split",
    }
    headers = {
        "APCA-API-KEY-ID": config.alpaca_api_key_id,
        "APCA-API-SECRET-KEY": config.alpaca_api_secret_key,
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return None

    data = response.json().get("bars", [])
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df.rename(
        columns={"t": "Date", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"},
        inplace=True,
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df.sort_values("Date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
