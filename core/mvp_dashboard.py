import streamlit as st
import pandas as pd
import plotly.graph_objects as go

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
        # Your login/register code here (keep it)
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

    st.subheader("Indicators")
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
        with c3: ind["period"] = st.number_input("Period", 1, 300, ind.get("period", 14), key=f"per{i}")
        with c4:
            if st.button("🗑", key=f"del{i}"):
                st.session_state.indicators.pop(i)
                st.rerun()

    if st.button("＋ Add Indicator"):
        st.session_state.indicators.append({"name": f"ind{len(st.session_state.indicators)+1}", "type": "ema", "period": 20})
        st.rerun()

    st.subheader("Long Entry Conditions")
    if "entry_long" not in st.session_state:
        st.session_state.entry_long = []

    for i, cond in enumerate(st.session_state.entry_long):
        c1, c2, c3, c4 = st.columns([3,1,3,1])
        with c1: cond["left"] = st.text_input("Left", cond["left"], key=f"el_left{i}")
        with c2: cond["op"] = st.selectbox("Op", OPERATORS, index=OPERATORS.index(cond["op"]), key=f"el_op{i}")
        with c3: cond["right"] = st.text_input("Right", cond["right"], key=f"el_right{i}")
        with c4:
            if st.button("🗑", key=f"del_el{i}"):
                st.session_state.entry_long.pop(i)
                st.rerun()

    if st.button("＋ Add Long Entry Condition"):
        st.session_state.entry_long.append({"left": "close", "op": ">", "right": "ema20"})
        st.rerun()

    if st.button("Run Backtest", type="primary"):
        with st.spinner("Loading data..."):
            df = load_ohlcv(market, timeframe, years)
            if df.empty:
                st.stop()

        with st.spinner("Backtesting..."):
            ind_cfg = [{"name": i["name"], "type": i["type"], "period": i.get("period", 14)} for i in st.session_state.indicators]

            entry_long = st.session_state.get("entry_long", [])

            cfg_dict = {
                "name": "User Strategy",
                "market": market,
                "timeframe": timeframe,
                "indicators": ind_cfg,
                "entry": {"long": [{"all": entry_long}] if entry_long else [], "short": []},
                "exit": {"long": [], "short": []},
                "risk": {"capital": 10000, "risk_per_trade_pct": 1.0}
            }

            cfg = parse_strategy_yaml(str(cfg_dict))

            df, skipped = apply_all_indicators(df, cfg)

            if skipped:
                for w in skipped:
                    st.warning(w)

            result = run_backtest_v2(df, cfg)

        metrics = result["metrics"]
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

        if st.button("Save Strategy"):
            name = st.text_input("Name", "V4 Strategy")
            ok, msg = save_user_strategy(st.session_state.email, name, str(cfg_dict))
            st.success(msg) if ok else st.error(msg)
