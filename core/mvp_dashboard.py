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

def run_mvp_dashboard():
    st.title("VectorAlgoAI – Crash-Test Lab **V4**")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
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

    st.subheader("Entry & Exit (placeholder)")
    st.info("Entry/exit conditions not implemented yet – backtest may give 0 trades")

    if st.button("Run Backtest", type="primary"):
        with st.spinner("Loading data..."):
            df = load_ohlcv(market, timeframe, years)
            if df.empty:
                st.stop()

        with st.spinner("Running backtest..."):
            ind_cfg = [{"name": i["name"], "type": i["type"], "period": i["period"]} for i in st.session_state.indicators]

            cfg_dict = {
                "name": "V4 Test",
                "market": market,
                "timeframe": timeframe,
                "indicators": ind_cfg,
                "entry": {"long": [], "short": []},
                "exit": {"long": [], "short": []},
                "risk": {"capital": 10000, "risk_per_trade_pct": 1.0}
            }
# Temporary debug: add loose entry condition so we get some trades
if not st.session_state.get("entry_long") and not st.session_state.get("entry_short"):
    st.info("No entry conditions → adding default for testing: close > ema20 (long)")
    st.session_state.entry_long = [{"left": "close", "op": ">", "right": "ema20"}]
            cfg = parse_strategy_yaml(str(cfg_dict))

            df, skipped = apply_all_indicators(df, cfg)

            if skipped:
                for w in skipped:
                    st.warning(w)

            result = run_backtest_v2(df, cfg, slippage_pct=0.0008, commission_per_trade=3.0, monte_carlo_runs=500)

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

        # Guarded per-indicator impact
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
            st.info("No trades → cannot calculate correlation")

        if st.button("💾 Save Strategy"):
            name = st.text_input("Name", "V4 Strategy")
            ok, msg = save_user_strategy(st.session_state.email, name, str(cfg_dict))
            st.success(msg) if ok else st.error(msg)

