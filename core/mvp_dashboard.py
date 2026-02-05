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

# Constants
MARKETS = ["NAS100", "US30", "SPX500", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
OPERATORS = [">", "<", ">=", "<=", "=="]

def run_mvp_dashboard():
    st.title("VectorAlgoAI – Crash-Test Lab **V4**")

    # Auth (keep your login code – omitted for brevity)
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        # Your auth tabs here
        return

    # Sidebar
    with st.sidebar:
        st.header("Market & Data")
        market = st.selectbox("Market", MARKETS, index=0)
        timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=3)
        years = st.slider("Years", 0.1, 5.0, 1.5, 0.1)

    # Indicators builder
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
        with c3: ind["period"] = st.number_input("Period", 1, 300, ind["period"], key=f"per{i}")
        with c4:
            if st.button("🗑", key=f"del{i}"):
                st.session_state.indicators.pop(i)
                st.rerun()

    if st.button("＋ Add Indicator"):
        st.session_state.indicators.append({"name": f"ind{len(st.session_state.indicators)+1}", "type": "ema", "period": 20})
        st.rerun()

    # Entry/Exit builder (simplified – expand later)
    st.subheader("Entry & Exit (placeholder – add full builder)")
    st.info("Entry/exit conditions not implemented yet – backtest may give 0 trades")

    # Run
    if st.button("Run Backtest", type="primary"):
        with st.spinner("Loading..."):
            df = load_ohlcv(market, timeframe, years)
            if df.empty:
                st.stop()

            ind_cfg = [{"name": i["name"], "type": i["type"], "period": i["period"]} for i in st.session_state.indicators]

            cfg_dict = {
                "name": "Test",
                "market": market,
                "timeframe": timeframe,
                "indicators": ind_cfg,
                "entry": {"long": [], "short": []},
                "exit": {"long": [], "short": []},
                "risk": {"capital": 10000, "risk_per_trade_pct": 1.0}
            }

            cfg = parse_strategy_yaml(str(cfg_dict))

            df, skipped = apply_all_indicators(df, cfg)

            if skipped:
                for w in skipped:
                    st.warning(w)

            result = run_backtest_v2(df, cfg, slippage_pct=0.0008, commission_per_trade=3.0, monte_carlo_runs=500)

        st.success("Backtest done")
        st.write(result["metrics"])

        if not result["trades_df"].empty:
            st.line_chart(result["equity_series"])
        else:
            st.info("0 trades – try relaxing entry conditions or different market/timeframe")
