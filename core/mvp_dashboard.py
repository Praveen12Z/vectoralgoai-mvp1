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

# ──────────────────────────────────────────────────────────────
# DASHBOARD MAIN FUNCTION
# ──────────────────────────────────────────────────────────────
def run_mvp_dashboard():
    st.title("VectorAlgoAI – Crash-Test Lab **V4**")
    st.caption("Regime • Slippage • Commissions • Monte Carlo • Indicator Impact")

    # Auth (keep your existing login/register code here – abbreviated)
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

    # ───── SIDEBAR ─────
    with st.sidebar:
        st.write(f"**{st.session_state.email}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        st.header("Market & Data")
        market = st.selectbox("Market", MARKETS, index=0)
        timeframe = st.selectbox("Timeframe", TIMEFRAMES, index=3)
        years = st.slider("Years of History", 0.2, 5.0, 1.5, 0.1)

        st.info("Free Polygon tier → very limited calls. Wait 5–15 min between tests.")

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
        with c1:
            ind["name"] = st.text_input("Name", ind["name"], key=f"ind_name_{i}")
        with c2:
            ind["type"] = st.selectbox("Type", list(INDICATOR_REGISTRY.keys()),
                                        index=list(INDICATOR_REGISTRY.keys()).index(ind["type"]), key=f"ind_type_{i}")
        with c3:
            ind["period"] = st.number_input("Period", 1, 300, ind["period"], key=f"ind_per_{i}")
        with c4:
            if st.button("🗑", key=f"ind_del_{i}"):
                st.session_state.indicators.pop(i)
                st.rerun()

    if st.button("＋ Add Indicator"):
        st.session_state.indicators.append({"name": f"ind_{len(st.session_state.indicators)+1}", "type": "ema", "period": 20})
        st.rerun()

    # ───── ENTRY / EXIT BUILDER (placeholder – expand later) ─────
    st.subheader("Entry & Exit (placeholder)")
    st.info("Entry/exit conditions not implemented yet – backtest may give 0 trades")

    # ───── RUN BUTTON ─────
    if st.button("🚀 Run V4 Backtest", type="primary", use_container_width=True):
        with st.spinner("Loading data..."):
            df = load_ohlcv(market, timeframe, years)
            if df.empty:
                st.stop()

        with st.spinner("Building strategy & backtesting..."):
            # Build indicators config
            ind_cfg = [{"name": i["name"], "type": i["type"], "period": i["period"]} for i in st.session_state.indicators]

            # Build minimal cfg (entry/exit empty for now)
            cfg_dict = {
                "name": "V4 UI Strategy",
                "market": market,
                "timeframe": timeframe,
                "indicators": ind_cfg,
                "entry": {"long": [], "short": []},
                "exit": {"long": [], "short": []},
                "risk": {"capital": 10000, "risk_per_trade_pct": 1.0}
            }

            cfg = parse_strategy_yaml(str(cfg_dict))

            # Apply indicators – returns (df, skipped list)
            df, skipped_indicators = apply_all_indicators(df, cfg)

            # Show skipped indicators safely
            if skipped_indicators:
                for warn in skipped_indicators:
                    st.warning(warn)

            # Run backtest
            result = run_backtest_v2(
                df,
                cfg,
                slippage_pct=0.0008,
                commission_per_trade=3.0,
                monte_carlo_runs=500
            )

        # ───── RESULTS ─────
        metrics = result["metrics"]
        trades_df = result["trades_df"]
        equity_series = result["equity_series"]
        mc = result.get("monte_carlo", {})
        regime_stats = result.get("regime_stats", {})

        st.success(f"Backtest complete – {len(df)} bars | {metrics['num_trades']} trades")

        # Core metrics
        cols = st.columns(5)
        cols[0].metric("Total Return", f"{metrics['total_return_pct']:.2f}%")
        cols[1].metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        cols[2].metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%")
        cols[3].metric("Max DD", f"{metrics['max_drawdown_pct']:.1f}%")
        cols[4].metric("Trades", metrics["num_trades"])

        # Equity curve
        st.subheader("Equity Curve (with slippage & commissions)")
        st.line_chart(equity_series)

        # Monte Carlo
        if mc:
            st.subheader("Monte Carlo (500 runs)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Mean Return", f"{mc['mean_return']:.2f}%")
            c2.metric("Median Return", f"{mc['median_return']:.2f}%")
            c3.metric("Worst 5%", f"{mc['worst_5pct']:.2f}%")

        # Regime stats
        if regime_stats:
            st.subheader("Performance by Regime")
            st.dataframe(pd.DataFrame(regime_stats))

        # Per-indicator impact – guarded against 0 trades
        st.subheader("Indicator Impact on PnL")
        impact = []
        if not trades_df.empty and "pnl" in trades_df.columns:
            pnl_series = trades_df["pnl"].reindex(df.index, method="ffill").fillna(0)
            for ind in st.session_state.indicators:
                col = ind["name"]
                if col in df.columns:
                    corr = df[col].corr(pnl_series)
                    impact.append({
                        "Indicator": col,
                        "Type": ind["type"].upper(),
                        "Period": ind["period"],
                        "Corr to PnL": round(corr, 3)
                    })
            if impact:
                st.dataframe(pd.DataFrame(impact).sort_values("Corr to PnL", ascending=False), use_container_width=True)
            else:
                st.info("No indicators with valid data")
        else:
            st.info("No trades generated → cannot compute correlation to PnL")

        # Save strategy
        if st.button("💾 Save Strategy"):
            name = st.text_input("Strategy Name", "V4 Custom")
            yaml_text = f"""name: "{name}"
market: "{market}"
timeframe: "{timeframe}"
indicators: {st.session_state.indicators}
entry: {{long: [], short: []}}
exit: {{long: [], short: []}}
risk: {{capital: 10000, risk_per_trade_pct: 1.0}}"""
            ok, msg = save_user_strategy(st.session_state.email, name, yaml_text)
            st.success(msg) if ok else st.error(msg)
