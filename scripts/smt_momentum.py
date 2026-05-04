"""
SMT 米国株式モメンタムファンド スクリーナー
SMTAM「SMT 米国株式モメンタムファンド」の選定ロジックを再現し、LINE通知する
"""
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date
import warnings, time, os
warnings.filterwarnings("ignore")

# ── LINE通知用 ────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.config import get_config
from app.notifier import LineMessagingNotifier

# ── スクリーナー ──────────────────────────────────────────────
UNIVERSE_FILE = os.path.join(os.path.dirname(__file__),
                              "..", "us_smt_universe.txt")
LOOKBACKS = {"6M": 126, "12M": 252, "36M": 756}
TOP_N = 7
MIN_AVG_VOL = 1_000_000
REBALANCE_MONTHS = [2, 5, 8, 11]

today = date.today()

with open(UNIVERSE_FILE) as f:
    universe = [l.strip() for l in f if l.strip()]

print(f"価格データ取得中... ({len(universe)}銘柄)", flush=True)
BATCH = 100
all_closes = {}
all_volumes = {}

for i in range(0, len(universe), BATCH):
    batch = universe[i:i+BATCH]
    try:
        raw = yf.download(batch, period="4y", auto_adjust=True,
                          progress=False, threads=True, timeout=30)
        if raw.empty:
            continue
        close_df = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        vol_df   = raw["Volume"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]
        for tk in batch:
            try:
                if tk in close_df.columns:
                    s = close_df[tk].dropna()
                    if len(s) >= 30:
                        all_closes[tk] = s
                if tk in vol_df.columns:
                    all_volumes[tk] = vol_df[tk].dropna()
            except Exception:
                pass
    except Exception:
        pass
    time.sleep(0.3)

liquid = [tk for tk in all_closes
          if len(all_volumes.get(tk, pd.Series())) >= 20
          and all_volumes.get(tk, pd.Series()).iloc[-20:].mean() >= MIN_AVG_VOL]


def calc_return(s, n):
    arr = s.values
    if len(arr) < n + 1:
        return None
    return float((arr[-1] / arr[-n-1] - 1) * 100)


period_returns = {
    tk: {p: calc_return(all_closes[tk], d) for p, d in LOOKBACKS.items()}
    for tk in liquid
}

results = {}
for period in ["6M", "12M", "36M"]:
    cands = [{"ticker": tk, "return": period_returns[tk][period]}
             for tk in liquid if period_returns[tk][period] is not None]
    cands.sort(key=lambda x: x["return"], reverse=True)
    results[period] = cands[:TOP_N]

m6  = [r["ticker"] for r in results["6M"]]
m12 = [r["ticker"] for r in results["12M"]]
m36 = [r["ticker"] for r in results["36M"]]

# ---- 1表にまとめ: 6M優先→12M→36M順 ----
def sort_key(tk):
    if tk in m6:
        return (0, -(period_returns[tk]["6M"] or 0))
    elif tk in m12:
        return (1, -(period_returns[tk]["12M"] or 0))
    else:
        return (2, -(period_returns[tk]["36M"] or 0))

all_sel = sorted(set(m6 + m12 + m36), key=sort_key)
n_holdings = len(all_sel)
weight = 100.0 / n_holdings

# 銘柄名・時価総額取得
print(f"銘柄名・時価総額取得中... ({len(all_sel)}銘柄)", flush=True)
names   = {}
mktcaps = {}
for tk in all_sel:
    try:
        info = yf.Ticker(tk).info
        names[tk]   = info.get("shortName", tk)[:28]
        mktcaps[tk] = info.get("marketCap")
    except Exception:
        names[tk]   = tk
        mktcaps[tk] = None
    time.sleep(0.4)


def next_rebal(today):
    for m in sorted(REBALANCE_MONTHS):
        if m > today.month:
            return f"{today.year}年{m}月末"
        elif m == today.month:
            return f"{today.year}年{m}月末（今月）"
    return f"{today.year+1}年{REBALANCE_MONTHS[0]}月末"


def fmt_r(r):
    if r is None:
        return "—"
    return f"+{r:,.1f}%" if r >= 0 else f"{r:,.1f}%"


def fmt_mktcap_us(mc):
    if mc is None or mc == 0:
        return "—"
    if mc >= 1e12:
        return f"${mc/1e12:.2f}T"
    return f"${mc/1e9:.1f}B"


def period_badge(tk):
    badges = []
    if tk in m6:  badges.append("6M")
    if tk in m12: badges.append("12M")
    if tk in m36: badges.append("36M")
    return " / ".join(badges)


# ---- markdown出力 ----
print()
print(f"## SMT 米国株式モメンタムファンド 選定結果（{today}）")
print()
print(f"**選定基準日**: {today}  ")
print(f"**次回リバランス**: {next_rebal(today)}  ")
print(f"**ユニバース**: 米国上場株・時価総額上位{len(universe)}銘柄"
      f"（流動性通過: {len(liquid)}銘柄）  ")
print(f"**選定銘柄数**: {n_holdings}銘柄 / 均等配分: {weight:.2f}%")
print()
print("---")
print()
print("| 順 | Ticker | 銘柄名 | 選出期間 | 時価総額 | 6M騰落率 | 12M騰落率 | 36M騰落率 | 配分 |")
print("|---:|--------|--------|----------|--------:|--------:|----------:|----------:|-----:|")

for rank, tk in enumerate(all_sel, 1):
    r6  = fmt_r(period_returns[tk]["6M"])
    r12 = fmt_r(period_returns[tk]["12M"])
    r36 = fmt_r(period_returns[tk]["36M"])
    name  = names.get(tk, tk)
    badge = period_badge(tk)
    mc    = fmt_mktcap_us(mktcaps.get(tk))
    print(f"| {rank} | {tk} | {name} | {badge} | {mc} | {r6} | {r12} | {r36} | {weight:.1f}% |")

print()
print("---")
print()
print("> 並び順: 6M選出（6M騰落率降順）→ 12M選出（12M騰落率降順）→ 36M選出（36M騰落率降順）")

# ---- LINE通知 -------------------------------------------------------
def build_line_message() -> str:
    lines = [
        f"📊 SMT米国モメンタム ({today})",
        f"次回リバランス: {next_rebal(today)}",
        f"選定 {n_holdings}銘柄 / 均等 {weight:.1f}%",
        f"流動性通過: {len(liquid)}/{len(universe)}銘柄",
        "─" * 24,
    ]
    for rank, tk in enumerate(all_sel, 1):
        badge = period_badge(tk)
        mc    = fmt_mktcap_us(mktcaps.get(tk))
        r6    = fmt_r(period_returns[tk]["6M"])
        r12   = fmt_r(period_returns[tk]["12M"])
        r36   = fmt_r(period_returns[tk]["36M"])
        name  = names.get(tk, tk)[:18]
        lines.append(f"{rank:>2}. {tk:<6} [{badge}] {mc}")
        lines.append(f"    {name}")
        lines.append(f"    6M:{r6} 12M:{r12} 36M:{r36}")
    lines += ["─" * 24, "SMTAM選定ロジック再現（参考）"]
    return "\n".join(lines)

config = get_config()
if config.line_channel_access_token and config.line_target_user_id:
    notifier = LineMessagingNotifier(
        config.line_channel_access_token,
        config.line_target_user_id,
    )
    notifier.send(build_line_message())
    print("\nLINE通知を送信しました")
else:
    print("\nLINE認証情報が未設定のためスキップ", file=sys.stderr)
