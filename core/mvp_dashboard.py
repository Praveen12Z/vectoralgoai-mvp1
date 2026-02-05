import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

from .data_loader import load_ohlcv
from .indicators import apply_all_indicators, INDICATOR_REGISTRY
from .strategy_config import parse_strategy_yaml
from .backtester_adapter import run_backtest_v2
from .auth import authenticate_user, register_user
from .strategy_store import load_user_strategies, save_user_strategy, delete_user_strategy

MARKETS = ["NAS100", "US30", "SPX500", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
OPERATORS = [">", "<", ">=", "<=", "=="]

def run_mvp_dashboard():
    st.title("VectorAlgoAI – Crash-Test Lab **V4**")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.email = None

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["Login", "Register"])
        with tab1:
            with st.form("login"):
                email = st.text_input("Email")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    ok, msg = authenticate_user(email, pw)
                    if ok:
                        st.session_state.logged_in = True
                        st.session_state.email = email
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
        with tab2:
            with st.form("register"):
                reg_email = st.text_input("Email")
                pw1 = st.text_input("Password", type="password")
                pw2 = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account"):
                    ok, msg = register_user(reg_email, pw1, pw2)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
        return

    with st.sidebar:
        st.write(f"**{st.session_state.email}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        st.header("Market & Data")
        market = st.selectbox("Market", MARKETS, index=0)
        timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=3)
        years = st.slider("Years", 0.2, 5.0, 1.5, 0.1)

    # ───── INDICATORS BUILDER ─────
    st.subheader("1. Indicators")
    if "indicators" not in st.session_state:
        st.session_state.indicators = [
            {"name": "ema20", "type": "ema", "period": 20},
            {"name": "rsi14", "type": "rsi", "period": 14},
            {"name": "atr14", "type": "atr", "period": 14},
        ]

    for i, ind in enumerate(st.session_state.indicators):
        c1, c2, c3, c4 = st.columns([3,2,2,1])
        with c1: ind["name"] = st.text_input("Name", ind["name"], key=f"name{i}")
        with c2: ind["type"] = st.selectbox("Type", list(INDICATOR_REGISTRY.keys()), index=list(INDICATOR_REGISTRY.keys()).index(ind["type"]), key=f"type{i}")
        with c3:
            if ind["type"] == "macd":
                ind["fast"] = st.number_input("Fast", 5, 50, 12, key=f"fast{i}")
                ind["slow"] = st.number_input("Slow", 10, 100, 26, key=f"slow{i}")
                ind["signal"] = st.number_input("Signal", 3, 30, 9, key=f"signal{i}")
            else:
                ind["period"] = st.number_input("Period", 1, 300, ind.get("period", 14), key=f"per{i}")
        with c4:
            if st.button("🗑", key=f"del{i}"):
                st.session_state.indicators.pop(i)
                st.rerun()

    if st.button("＋ Add Indicator"):
        st.session_state.indicators.append({"name": f"ind{len(st.session_state.indicators)+1}", "type": "ema", "period": 20})
        st.rerun()

    # ───── ENTRY BUILDER ─────
    st.subheader("2. Entry Conditions")

    # Long
    st.markdown("**Long Entry (ALL must be true)**")
    if "entry_long" not in st.session_state:
        st.session_state.entry_long = []

    for i, cond in enumerate(st.session_state.entry_long):
        c1, c2, c3, c4 = st.columns([3,1,3,1])
        with c1: cond["left"] = st.text_input("Left (indicator or 'close')", cond["left"], key=f"el_left{i}")
        with c2: cond["op"] = st.selectbox("Operator", OPERATORS, index=OPERATORS.index(cond["op"]), key=f"el_op{i}")
        with c3: cond["right"] = st.text_input("Right (indicator or value)", cond["right"], key=f"el_right{i}")
        with c4:
            if st.button("🗑", key=f"del_el{i}"):
                st.session_state.entry_long.pop(i)
                st.rerun()

    if st.button("＋ Add Long Entry Condition"):
        st.session_state.entry_long.append({"left": "close", "op": ">", "right": "ema20"})
        st.rerun()

    # Short (optional)
    st.markdown("**Short Entry (ALL must be true)**")
    if "entry_short" not in st.session_state:
        st.session_state.entry_short = []

    for i, cond in enumerate(st.session_state.entry_short):
        c1, c2, c3, c4 = st.columns([3,1,3,1])
        with c1: cond["left"] = st.text_input("Left", cond["left"], key=f"es_left{i}")
        with c2: cond["op"] = st.selectbox("Operator", OPERATORS, index=OPERATORS.index(cond["op"]), key=f"es_op{i}")
        with c3: cond["right"] = st.text_input("Right", cond["right"], key=f"es_right{i}")
        with c4:
            if st.button("🗑", key=f"del_es{i}"):
                st.session_state.entry_short.pop(i)
                st.rerun()

    if st.button("＋ Add Short Entry Condition"):
        st.session_state.entry_short.append({"left": "close", "op": "<", "right": "ema20"})
        st.rerun()

    # ───── RUN BUTTON ─────
    if st.button("Run Backtest", type="primary"):
        with st.spinner("Loading data..."):
            df = load_ohlcv(market, timeframe, years)
            if df.empty:
                st.stop()

        with st.spinner("Backtesting..."):
            ind_cfg = []
            for i in st.session_state.indicators:
                item = {"name": i["name"], "type": i["type"]}
                if i["type"] == "macd":
                    item["fast"] = i.get("fast", 12)
                    item["slow"] = i.get("slow", 26)
                    item["signal"] = i.get("signal", 9)
                else:
                    item["period"] = i.get("period", 14)
                ind_cfg.append(item)

            entry_long = st.session_state.get("entry_long", [])
            entry_short = st.session_state.get("entry_short", [])

            if not entry_long and not entry_short:
                st.warning("No entry conditions defined → backtest will produce 0 trades. Add at least one long or short condition above.")

            cfg_dict = {
                "name": "User Strategy",
                "market": market,
                "timeframe": timeframe,
                "indicators": ind_cfg,
                "entry": {
                    "long": [{"all": entry_long}] if entry_long else [],
                    "short": [{"all": entry_short}] if entry_short else []
                },
                "exit": {"long": [], "short": []},
                "risk": {"capital": 10000, "risk_per_trade_pct": 1.0}
            }

            cfg = parse_strategy_yaml(str(cfg_dict))

            df, skipped = apply_all_indicators(df, cfg)

            if skipped:
                for w in skipped:
                    st.warning(w)

            result = run_backtest_v2(df, cfg, slippage_pct=0.0008, commission_per_trade=3.0, monte_carlo_runs=500)

        # ───── RESULTS ─────
        metrics = result["metrics"]
        trades_df = result["trades_df"]
        equity = result["equity_series"]

        st.success(f"Backtest complete – {len(df)} bars | {metrics['num_trades']} trades")

        cols = st.columns(5)
        cols[0].metric("Return", f"{metrics['total_return_pct']:.2f}%")
        cols[1].metric("PF", f"{metrics['profit_factor']:.2f}")
        cols[2].metric("Win %", f"{metrics['win_rate_pct']:.1f}%")
        cols[3].metric("Max DD", f"{metrics['max_drawdown_pct']:.1f}%")
        cols[4].metric("Trades", metrics["num_trades"])

        st.subheader("Equity Curve")
        st.line_chart(equity)

        st.subheader("Indicator Impact")
        if not trades_df.empty and "pnl" in trades_df.columns:
            pnl_series = trades_df["pnl"].reindex(df.index, method="ffill").fillna(0)
            impact = []
            for ind in st.session_state.indicators:
                col = ind["name"]
                if col in df.columns:
                    corr = df[col].corr(pnl_series)
                    impact.append({"Indicator": col, "Type": ind["type"].upper(), "Corr": round(corr, 3)})
            if impact:
                st.dataframe(pd.DataFrame(impact).sort_values("Corr", ascending=False))
        else:
            st.info("No trades → no correlation calculated")

        if st.button("Save Strategy"):
            name = st.text_input("Name", "My Strategy")
            ok, msg = save_user_strategy(st.session_state.email, name, str(cfg_dict))
            st.success(msg) if ok else st.error(msg)

