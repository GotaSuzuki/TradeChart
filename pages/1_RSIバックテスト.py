"""Streamlit page for RSI strategy backtesting."""

from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st

from app.backtest import run_rsi_backtest
from app.market_data import download_price_history

DEFAULT_TICKERS = ["NVDA", "AVGO", "NBIS", "MU", "GOOG", "SNDK", "STX"]
PERIOD_OPTIONS = {
    "1年": "1y",
    "2年": "2y",
    "3年": "3y",
    "5年": "5y",
}

st.set_page_config(page_title="RSIバックテスト", layout="wide")
st.title("RSIバックテスト")
st.markdown("RSIが指定値以下で買い、指定値以上で売るシンプル戦略を検証します。")


@st.cache_data(show_spinner=False, ttl=3600)
def _get_price_history(ticker: str, period: str) -> pd.DataFrame:
    return download_price_history(ticker, period=period)


def _parse_tickers(value: str) -> List[str]:
    raw_tokens = value.replace("\n", ",").split(",")
    tickers: List[str] = []
    seen = set()
    for token in raw_tokens:
        ticker = token.strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    return tickers


with st.form("rsi-backtest-form"):
    tickers_input = st.text_area(
        "対象銘柄 (カンマ区切り)",
        value=", ".join(DEFAULT_TICKERS),
        height=90,
    )
    left, right = st.columns(2)
    with left:
        buy_rsi = st.number_input(
            "RSI 以下で買い",
            min_value=1.0,
            max_value=99.0,
            value=40.0,
            step=1.0,
        )
    with right:
        sell_rsi = st.number_input(
            "RSI 以上で売り",
            min_value=1.0,
            max_value=99.0,
            value=70.0,
            step=1.0,
        )
    period_label = st.selectbox(
        "価格データ期間",
        options=list(PERIOD_OPTIONS.keys()),
        index=2,
    )
    run_clicked = st.form_submit_button("バックテスト実行", use_container_width=True)

if not run_clicked:
    st.caption(f"初期表示銘柄: {', '.join(DEFAULT_TICKERS)}")
else:
    if buy_rsi >= sell_rsi:
        st.warning("買い条件のRSIは、売り条件のRSIより小さくしてください。")
        st.stop()

    tickers = _parse_tickers(tickers_input)
    if not tickers:
        st.warning("銘柄を1つ以上入力してください。")
        st.stop()

    period = PERIOD_OPTIONS[period_label]
    rows = []
    curves = []
    failed = []

    with st.spinner("バックテスト実行中..."):
        for ticker in tickers:
            history = _get_price_history(ticker, period)
            result = run_rsi_backtest(ticker, history, buy_rsi, sell_rsi)
            if result is None:
                failed.append(ticker)
                continue

            rows.append(
                {
                    "Ticker": result.ticker,
                    "Strategy Return": result.strategy_return,
                    "Buy & Hold Return": result.buy_hold_return,
                    "Trades": result.trades,
                    "Latest RSI": result.latest_rsi,
                    "From": result.start_date.date(),
                    "To": result.end_date.date(),
                }
            )
            curve = result.equity_curve.copy()
            curve["Ticker"] = result.ticker
            curves.append(curve)

    if not rows:
        st.info("バックテスト結果を計算できませんでした。銘柄や期間を見直してください。")
        if failed:
            st.caption("データ不足の銘柄: " + ", ".join(failed))
        st.stop()

    result_df = pd.DataFrame(rows).sort_values("Strategy Return", ascending=False)
    display_df = result_df.copy()
    display_df["Strategy Return (%)"] = display_df["Strategy Return"] * 100.0
    display_df["Buy & Hold Return (%)"] = display_df["Buy & Hold Return"] * 100.0
    display_df = display_df[
        [
            "Ticker",
            "Strategy Return (%)",
            "Buy & Hold Return (%)",
            "Trades",
            "Latest RSI",
            "From",
            "To",
        ]
    ]
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("銘柄数", f"{len(result_df)}")
    with metric_col2:
        st.metric("平均 Strategy Return", f"{result_df['Strategy Return'].mean() * 100:.2f}%")
    with metric_col3:
        st.metric("平均 Buy & Hold Return", f"{result_df['Buy & Hold Return'].mean() * 100:.2f}%")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Strategy Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Buy & Hold Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Trades": st.column_config.NumberColumn(format="%d"),
            "Latest RSI": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    if curves:
        curve_df = pd.concat(curves, ignore_index=True)
        fig = px.line(
            curve_df,
            x="Date",
            y="Equity",
            color="Ticker",
            labels={"Date": "日付", "Equity": "資産推移 (初期=1.0)", "Ticker": "銘柄"},
            title="戦略の資産推移",
        )
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig, use_container_width=True)

    if failed:
        st.warning("データ不足で計算できなかった銘柄: " + ", ".join(failed))
