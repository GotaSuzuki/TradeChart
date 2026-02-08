"""Monitor tickers and send LINE notifications when RSI falls below threshold."""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.alerts import load_alerts
from app.config import get_config
from app.market_data import compute_rsi, download_price_history
from app.notifier import LineMessagingNotifier

DEFAULT_TICKERS = ["NVDA", "AVGO", "NBIS", "MU", "GOOG", "SNDK", "STX"]


def check_ticker(ticker: str, threshold: float) -> dict[str, object] | None:
    price_df = download_price_history(ticker)
    if price_df.empty:
        print(f"{ticker}: 価格データを取得できませんでした", file=sys.stderr)
        return None

    enriched = compute_rsi(price_df)
    latest = enriched.dropna(subset=["RSI"])
    if latest.empty:
        print(f"{ticker}: RSIを計算できませんでした", file=sys.stderr)
        return None

    row = latest.iloc[-1]
    rsi_value = row["RSI"]
    data_date = pd.to_datetime(row["Date"]).date()
    if rsi_value <= threshold:
        print(f"{ticker}: RSI {rsi_value:.1f} が閾値以下です")
        return {
            "ticker": ticker,
            "rsi": float(rsi_value),
            "threshold": float(threshold),
            "date": data_date,
        }
    else:
        print(f"{ticker}: RSI {rsi_value:.1f} は閾値を上回っています")
    return None


def format_alert_message(matches: list[dict[str, object]]) -> str:
    dates = {match["date"] for match in matches if isinstance(match.get("date"), date)}
    if len(dates) == 1:
        only_date = next(iter(dates))
        header = f"RSIアラート ({only_date.isoformat()})"
    else:
        header = "RSIアラート"

    lines = [header]
    for match in matches:
        ticker = match.get("ticker", "")
        rsi_value = match.get("rsi", 0.0)
        threshold = match.get("threshold", 0.0)
        line = f"{ticker} RSI {rsi_value:.1f} (<= {threshold:.1f})"
        if len(dates) != 1 and isinstance(match.get("date"), date):
            line = f"{line} on {match['date'].isoformat()}"
        lines.append(line)
    return "\n".join(lines)


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
        tickers = sorted(alert_map.keys())
    else:
        tickers = sorted(set(tickers))

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
    matches = []
    for ticker in tickers:
        threshold = alert_map.get(ticker.upper(), config.rsi_alert_threshold)
        result = check_ticker(ticker.upper(), float(threshold))
        if result:
            matches.append(result)

    if matches:
        message = format_alert_message(matches)
        notifier.send(message)
        print(f"LINE通知を送信しました ({len(matches)} 件まとめて送信)")
    else:
        print("該当するRSIアラートはありませんでした")


if __name__ == "__main__":
    main()
