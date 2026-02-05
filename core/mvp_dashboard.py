import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

from .data_loader import load_ohlcv
from .indicators import apply_all_indicators, INDICATOR_REGISTRY
from .strategy_config import parse_strategy_yaml
from .backtester_adapter import run_backtest_v2
from .auth import authenticate_user, register_user
from .strategy_store import load_user_strategies, save_user_strategy, delete_user_strategy

# ──────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────
MARKETS = [
    "NAS100", "US30", "SPX500",
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "EURJPY", "GBPJPY",
    "XAUUSD", "XAGUSD"
]

TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
OPERATORS = [">", "<", ">=", "<=", "=="]

# ──────────────────────────────────────────────────────────────
# MAIN DASHBOARD
# ──────────────────────────────────────────────────────────────
def run_mvp_dashboard():
    st.title("VectorAlgoAI – Crash-Test Lab **V4** (Regime + Slippage + Monte Carlo + Attribution)")

    # ───── AUTH ─────
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        # Your existing login/register code here (keep it)
        return

    st.sidebar.write(f"**{st.session_state.email}**")

    # ───── MARKET SETTINGS ─────
    with st.sidebar:
        st.header("Market & Data")
        market = st.selectbox("Market", MARKETS, index=0)
        timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=3)
        years = st.slider("Years of History", 0.2, 5.0, 1.5, 0.1)
        st.caption("Free Polygon tier → wait 5–10 min between tests")

    # ───── INDICATOR BUILDER ─────
    st.subheader("1. Indicators")
    if "indicators" not in st.session_state:
        st.session_state.indicators = [
            {"name": "ema20", "type": "ema", "period": 20},
            {"name": "rsi14", "type": "rsi", "period": 14},
            {"name": "atr14", "type": "atr", "period": 14},
        ]

    for i, ind in enumerate(st.session_state.indicators):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        with c1: ind["name"] = st.text_input("Name", ind["name"], key=f"n{i}")
        with c2: ind["type"] = st.selectbox("Type", list(INDICATOR_REGISTRY.keys()), index=list(INDICATOR_REGISTRY.keys()).index(ind["type"]), key=f"t{i}")
        with c3: ind["period"] = st.number_input("Period", 1, 300, ind["period"], key=f"p{i}")
        with c4:
            if st.button("🗑", key=f"d{i}"):
                st.session_state.indicators.pop(i)
                st.rerun()

    if st.button("＋ Add Indicator"):
        st.session_state.indicators.append({"name": f"ind{len(st.session_state.indicators)+1}", "type": "ema", "period": 20})
        st.rerun()

    # ───── ENTRY / EXIT BUILDER ─────
    def cond_builder(key, title):
        st.subheader(title)
        if st.button("＋ Add Condition", key=f"add_{key}"):
            st.session_state[key].append({"left": "close", "op": ">", "right": "ema20"})
            st.rerun()
        for i, c in enumerate(st.session_state[key]):
            c1, c2, c3, c4 = st.columns([3,1,3,1])
            with c1: c["left"] = st.text_input("Left", c["left"], key=f"{key}_l{i}")
            with c2: c["op"] = st.selectbox("Op", OPERATORS, index=OPERATORS.index(c["op"]), key=f"{key}_o{i}")
            with c3: c["right"] = st.text_input("Right", c["right"], key=f"{key}_r{i}")
            with c4:
                if st.button("🗑", key=f"{key}_del{i}"):
                    st.session_state[key].pop(i)
                    st.rerun()

    col_e, col_x = st.columns(2)
    with col_e:
        if "entry_long" not in st.session_state: st.session_state.entry_long = []
        if "entry_short" not in st.session_state: st.session_state.entry_short = []
        cond_builder("entry_long", "Long Entry (ALL true)")
        cond_builder("entry_short", "Short Entry (ALL true)")
    with col_x:
        if "exit_long" not in st.session_state: st.session_state.exit_long = []
        if "exit_short" not in st.session_state: st.session_state.exit_short = []
        cond_builder("exit_long", "Long Exit")
        cond_builder("exit_short", "Short Exit")

    # ───── RUN BUTTON ─────
    if st.button("🚀 RUN V4 BACKTEST (Slippage + Regime + Monte Carlo)", type="primary", use_container_width=True):
        with st.spinner("Fetching data..."):
            df_price = load_ohlcv(market, timeframe, years)
            if df_price.empty: st.stop()

        with st.spinner("Building strategy + backtesting..."):
            # Build indicators
            ind_cfg = [{"name": i["name"], "type": i["type"], "period": i["period"]} for i in st.session_state.indicators]

            # Build entry/exit
            entry = {
                "long": [{"all": st.session_state.entry_long}] if st.session_state.entry_long else [],
                "short": [{"all": st.session_state.entry_short}] if st.session_state.entry_short else []
            }
            exit_ = {
                "long": [{"all": st.session_state.exit_long}] if st.session_state.exit_long else [],
                "short": [{"all": st.session_state.exit_short}] if st.session_state.exit_short else []
            }

            cfg_dict = {
                "name": "V4 Strategy",
                "market": market,
                "timeframe": timeframe,
                "indicators": ind_cfg,
                "entry": entry,
                "exit": exit_,
                "risk": {"capital": 10000, "risk_per_trade_pct": 1.0}
            }
            cfg = parse_strategy_yaml(str(cfg_dict))

            df = apply_all_indicators(df_price, cfg)

            # Run enhanced backtester
            result = run_backtest_v2(
                df, cfg,
                slippage_pct=0.0008,
                commission_per_trade=3.0,
                monte_carlo_runs=800
            )

        # ───── RESULTS ─────
        metrics = result["metrics"]
        trades_df = result["trades_df"]
        equity = result["equity_series"]
        mc = result.get("monte_carlo", {})
        regime_stats = result.get("regime_stats", {})

        st.success(f"Backtest complete – {len(df)} bars | {metrics['num_trades']} trades")

        c = st.columns(5)
        c[0].metric("Return", f"{metrics['total_return_pct']:.2f}%")
        c[1].metric("PF", f"{metrics['profit_factor']:.2f}")
        c[2].metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%")
        c[3].metric("Max DD", f"{metrics['max_drawdown_pct']:.1f}%")
        c[4].metric("Trades", metrics["num_trades"])

        st.subheader("Equity Curve (Slippage + Commissions)")
        st.line_chart(equity)

        if mc:
            st.subheader("Monte Carlo (800 runs)")
            st.write(f"Mean: **{mc['mean_return']:.2f}%** | Median: **{mc['median_return']:.2f}%** | 5% worst: **{mc['worst_dd_95']:.2f}%**")

        if regime_stats:
            st.subheader("Regime Breakdown")
            st.dataframe(pd.DataFrame(regime_stats))

        # Per-indicator impact
        st.subheader("Indicator Impact")
        impact = []
        for i in st.session_state.indicators:
            col = i["name"]
            if col in df.columns:
                corr = df[col].corr(trades_df["pnl"].reindex(df.index, method="ffill").fillna(0))
                impact.append({"Indicator": col, "Type": i["type"].upper(), "Corr to PnL": round(corr, 3)})
        if impact:
            st.dataframe(pd.DataFrame(impact).sort_values("Corr to PnL", ascending=False), use_container_width=True)

        # Save
        if st.button("💾 Save Strategy"):
            name = st.text_input("Name", "V4 Strategy")
            yaml = f"name: \"{name}\"\nmarket: \"{market}\"\ntimeframe: \"{timeframe}\"\nindicators: {st.session_state.indicators}\nentry: {entry}\nexit: {exit_}\nrisk: {{capital: 10000, risk_per_trade_pct: 1.0}}"
            ok, msg = save_user_strategy(st.session_state.email, name, yaml)
            st.success(msg) if ok else st.error(msg)
