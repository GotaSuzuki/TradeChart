"""Streamlit portfolio page."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from app.market_data import download_price_history
from app.portfolio import delete_holding, load_holdings, upsert_holding

COLOR_PALETTE = [
    "#4C78A8",
    "#F58518",
    "#E45756",
    "#72B7B2",
    "#54A24B",
    "#EECA3B",
    "#B279A2",
    "#FF9DA6",
    "#9D755D",
    "#BAB0AC",
    "#1F77B4",
    "#2CA02C",
    "#D62728",
    "#9467BD",
    "#8C564B",
]

st.set_page_config(page_title="ポートフォリオ", layout="wide")
st.title("ポートフォリオ")
st.markdown("保有株の登録、現在株価、評価額、構成比を表示します。")


@st.cache_data(show_spinner=False, ttl=1800)
def _get_latest_price(ticker: str) -> Tuple[Optional[float], Optional[pd.Timestamp]]:
    try:
        price_df = download_price_history(ticker, period="1y")
    except Exception:
        return None, None

    if price_df is None or price_df.empty or "Close" not in price_df.columns:
        return None, None
    clean = price_df.dropna(subset=["Close"]).copy()
    if clean.empty:
        return None, None
    last = clean.iloc[-1]
    price = float(last["Close"])
    date = pd.to_datetime(last.get("Date"))
    return price, date


@st.cache_data(show_spinner=False, ttl=1800)
def _get_usd_jpy_rate() -> Tuple[Optional[float], Optional[pd.Timestamp]]:
    try:
        fx_df = download_price_history("JPY=X", period="1mo")
    except Exception:
        return None, None
    if fx_df is None or fx_df.empty or "Close" not in fx_df.columns:
        return None, None
    clean = fx_df.dropna(subset=["Close"]).copy()
    if clean.empty:
        return None, None
    last = clean.iloc[-1]
    rate = float(last["Close"])
    date = pd.to_datetime(last.get("Date"))
    return rate, date


def _build_rows(
    holdings: List[Dict[str, object]], usd_jpy_rate: Optional[float]
) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for holding in holdings:
        ticker = str(holding.get("ticker", "")).strip().upper()
        shares = int(holding.get("shares", 0))
        usd_price, price_date = _get_latest_price(ticker)
        jpy_price = usd_price * usd_jpy_rate if usd_price is not None and usd_jpy_rate else None
        jpy_value = jpy_price * shares if jpy_price is not None else None
        rows.append(
            {
                "id": holding.get("id"),
                "ticker": ticker,
                "shares": shares,
                "price_jpy": jpy_price,
                "value_jpy": jpy_value,
                "price_date": price_date,
            }
        )
    return rows


left_col, right_col = st.columns([1.1, 1.4], gap="large")

with left_col:
    st.subheader("保有株の登録")
    with st.form("portfolio-add-form"):
        ticker_input = st.text_input("ティッカー", value="", placeholder="NVDA")
        shares_input = st.number_input(
            "保有数",
            min_value=1,
            value=1,
            step=1,
            format="%d",
            help="整数のみ入力できます。",
        )
        submitted = st.form_submit_button("追加 / 更新")
        if submitted:
            ticker = ticker_input.strip().upper()
            if not ticker:
                st.warning("ティッカーを入力してください。")
            else:
                upsert_holding(ticker=ticker, shares=int(shares_input))
                st.success(f"{ticker} を登録しました。")

    st.divider()

    holdings = load_holdings()
    if not holdings:
        st.subheader("保有一覧")
        st.info("まだ保有株が登録されていません。")
    else:
        usd_jpy_rate, fx_date = _get_usd_jpy_rate()
        if usd_jpy_rate is None:
            st.warning("為替レート(USD/JPY)を取得できませんでした。円表示できないため、時間をおいて再実行してください。")
            st.stop()

        df = pd.DataFrame(_build_rows(holdings, usd_jpy_rate))
        df.sort_values("ticker", inplace=True)

        st.subheader("保有一覧")
        total_value = df["value_jpy"].sum(min_count=1)
        if pd.isna(total_value):
            st.metric("評価額合計", "-")
        else:
            st.metric("評価額合計", f"¥{total_value:,.0f}")
        if fx_date is not None:
            st.caption(f"為替レート: 1 USD = {usd_jpy_rate:,.2f} JPY ({fx_date.date()})")
        else:
            st.caption(f"為替レート: 1 USD = {usd_jpy_rate:,.2f} JPY")

        display_df = df.rename(
            columns={
                "ticker": "銘柄",
                "shares": "保有数",
                "price_jpy": "現在株価",
                "value_jpy": "評価額",
                "price_date": "価格日付",
            }
        )
        display_df = display_df[["銘柄", "保有数", "現在株価", "評価額", "価格日付"]]
        display_df["現在株価"] = display_df["現在株価"].map(
            lambda x: f"¥{x:,.0f}" if pd.notna(x) else "-"
        )
        display_df["評価額"] = display_df["評価額"].map(
            lambda x: f"¥{x:,.0f}" if pd.notna(x) else "-"
        )
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "保有数": st.column_config.NumberColumn(format="%d"),
                "価格日付": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
            },
        )

        st.subheader("保有株の削除")
        options = {f"{h['ticker']} ({h['shares']})": h["id"] for h in holdings}
        selected = st.selectbox("削除する銘柄", list(options.keys()))
        if st.button("選択した銘柄を削除"):
            delete_holding(options[selected])
            st.success("保有株を削除しました。再読込すると一覧に反映されます。")

with right_col:
    st.subheader("ポートフォリオ構成比")
    holdings = load_holdings()
    if not holdings:
        st.info("保有株がないため、構成比を表示できません。")
    else:
        usd_jpy_rate, _ = _get_usd_jpy_rate()
        if usd_jpy_rate is None:
            st.info("為替レートを取得できないため、構成比を表示できません。")
        else:
            df = pd.DataFrame(_build_rows(holdings, usd_jpy_rate))
            df.sort_values("ticker", inplace=True)
            plot_df = df.dropna(subset=["value_jpy"]).copy()
            total_value = plot_df["value_jpy"].sum(min_count=1)
            if plot_df.empty or pd.isna(total_value) or total_value <= 0:
                st.info("価格データが取得できず、構成比を計算できませんでした。")
            else:
                tickers = plot_df["ticker"].tolist()
                fig = px.pie(
                    plot_df,
                    names="ticker",
                    values="value_jpy",
                    color="ticker",
                    category_orders={"ticker": tickers},
                    color_discrete_sequence=COLOR_PALETTE,
                    title="ポートフォリオ構成比 (JPY)",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)

    st.caption("データソース: Yahoo Finance (yfinance) / Alpaca")
