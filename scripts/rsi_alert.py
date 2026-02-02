"""Monitor tickers and send LINE notifications when RSI falls below threshold."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

import pandas as pd

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.alerts import load_alerts
from app.config import get_config
from app.market_data import compute_rsi, download_price_history
from app.notifier import LineMessagingNotifier

DEFAULT_TICKERS = ["NVDA", "AVGO", "NBIS", "MU", "GOOG"]


def check_ticker(ticker: str, threshold: float, notifier: LineNotifier) -> None:
    price_df = download_price_history(ticker)
    if price_df.empty:
        print(f"{ticker}: 価格データを取得できませんでした", file=sys.stderr)
        return

    enriched = compute_rsi(price_df)
    latest = enriched.dropna(subset=["RSI"])
    if latest.empty:
        print(f"{ticker}: RSIを計算できませんでした", file=sys.stderr)
        return

    row = latest.iloc[-1]
    rsi_value = row["RSI"]
    date = row["Date"]
    if rsi_value <= threshold:
        message = (
            f"RSIアラート {ticker}: {rsi_value:.1f} (<= {threshold:.1f}) on "
            f"{pd.to_datetime(date).date()}"
        )
        notifier.send(message)
        print(f"{ticker}: LINE通知を送信しました ({rsi_value:.1f})")
    else:
        print(f"{ticker}: RSI {rsi_value:.1f} は閾値を上回っています")


def main() -> None:
    parser = argparse.ArgumentParser(description="RSI monitor with LINE notifications")
    parser.add_argument("tickers", nargs="*", help="監視するティッカー (例: NVDA AAPL)")
    args = parser.parse_args()
    tickers = args.tickers or DEFAULT_TICKERS
    run_alerts(tickers)


def run_alerts(tickers):
    alerts = load_alerts()
    alert_map = {}
    if alerts:
        for alert in alerts:
            ticker = (alert.get("ticker") or "").upper()
            threshold = alert.get("threshold")
            if ticker:
                alert_map[ticker] = threshold
        alert_tickers = set(alert_map.keys())
        tickers = sorted(set(tickers) | alert_tickers)

    config = get_config()
    if not config.line_channel_access_token or not config.line_target_user_id:
        print(
            "LINE Messaging APIのトークンまたはユーザーIDが設定されていません (環境変数 LINE_CHANNEL_ACCESS_TOKEN, LINE_TARGET_USER_ID を設定してください)",
            file=sys.stderr,
        )
        sys.exit(1)

    notifier = LineMessagingNotifier(
        config.line_channel_access_token,
        config.line_target_user_id,
    )
    for ticker in tickers:
        threshold = alert_map.get(ticker.upper(), config.rsi_alert_threshold)
        check_ticker(ticker.upper(), float(threshold), notifier)


if __name__ == "__main__":
    main()
