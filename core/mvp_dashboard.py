import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .data_loader import load_ohlcv
from .indicators import apply_all_indicators
from .strategy_config import parse_strategy_yaml, StrategyConfig
from .backtester_adapter import run_backtest_v2
from .strategy_store import load_user_strategies, save_user_strategy, delete_user_strategy
from .auth import authenticate_user, register_user

DEFAULT_YAML = """\
name: "NAS100 Momentum v5 – Pullback System"
market: "NAS100"
timeframe: "1h"

indicators:
  - name: ema20
    type: ema
    period: 20
    source: close
  - name: ema50
    type: ema
    period: 50
    source: close
  - name: ema200
    type: ema
    period: 200
    source: close
  - name: rsi14
    type: rsi
    period: 14
    source: close
  - name: atr14
    type: atr
    period: 14

entry:
  long:
    - left: ema20
      op: ">"
      right: ema50
    - left: ema50
      op: ">"
      right: ema200
    - left: close
      op: "<"
      right: ema20
    - left: close
      op: ">"
      right: ema50
    - left: rsi14
      op: "<"
      right: 55
    - left: rsi14
      op: ">"
      right: 40

  short:
    - left: ema20
      op: "<"
      right: ema50
    - left: ema50
      op: "<"
      right: ema200
    - left: close
      op: ">"
      right: ema20
    - left: close
      op: "<"
      right: ema50
    - left: rsi14
      op: ">"
      right: 45
    - left: rsi14
      op: "<"
      right: 60

exit:
  long:
    - type: atr_sl
      atr_col: atr14
      multiple: 2.0
    - type: atr_tp
      atr_col: atr14
      multiple: 3.5
  short:
    - type: atr_sl
      atr_col: atr14
      multiple: 2.0
    - type: atr_tp
      atr_col: atr14
      multiple: 3.5

risk:
  capital: 10000
  risk_per_trade_pct: 1.0
"""


def run_mvp_dashboard():
    st.title("VectorAlgoAI – Strategy Crash-Test Lab")

    # Simple session state login
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
                    success, msg = authenticate_user(email, pw)
                    if success:
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
                    success, msg = register_user(reg_email, pw1, pw2)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
        return

    # Logged in → main app
    st.write(f"Welcome back, **{st.session_state.email}**")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.email = None
        st.rerun()

    # Sidebar controls
    with st.sidebar:
        st.header("Controls")
        market = st.selectbox("Market", ["NAS100", "US30", "SPX500", "XAUUSD", "EURUSD"])
        timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"])
        years = st.slider("Years of history", 1, 10, 3)

    # Strategy input
    strategy_yaml = st.text_area("Strategy YAML", DEFAULT_YAML, height=400)

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Run Crash-Test", type="primary", use_container_width=True):
            with st.spinner("Loading data..."):
                df = load_ohlcv(market, timeframe, years)
                if df.empty:
                    st.error("No data loaded. Check symbol / connection.")
                    st.stop()

            with st.spinner("Applying indicators..."):
                try:
                    cfg = parse_strategy_yaml(strategy_yaml)
                    df = apply_all_indicators(df, cfg)
                except Exception as e:
                    st.error(f"Strategy parsing error: {str(e)}")
                    st.stop()

            with st.spinner("Running backtest..."):
                try:
                    result = run_backtest_v2(df, cfg)
                    metrics = result["metrics"]
                    trades_df = result["trades_df"]
                    weaknesses = result["weaknesses"]
                    suggestions = result["suggestions"]
                except Exception as e:
                    st.error(f"Backtest failed: {str(e)}")
                    st.stop()

            # Save strategy if wanted
            if st.button("💾 Save this strategy"):
                success, msg = save_user_strategy(st.session_state.email, cfg.name, strategy_yaml)
                st.toast(msg)

    # Results section
    if "metrics" in locals():
        st.subheader("Performance Summary")
        cols = st.columns(5)
        cols[0].metric("Total Return", f"{metrics['total_return_pct']:.2f}%")
        cols[1].metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        cols[2].metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%")
        cols[3].metric("Max DD", f"{metrics['max_drawdown_pct']:.1f}%")
        cols[4].metric("Trades", metrics["num_trades"])

        st.subheader("Equity Curve")
        if not trades_df.empty:
            equity = [10000] + list(trades_df["pnl"].cumsum() + 10000)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trades_df["exit_time"],
                y=equity[1:],
                mode="lines",
                name="Equity"
            ))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trades → no equity curve")

        st.subheader("Trade Log")
        st.dataframe(trades_df)

        colw, colsug = st.columns(2)
        with colw:
            st.subheader("Weaknesses")
            for w in weaknesses:
                st.warning(w)
        with colsug:
            st.subheader("Suggestions")
            for s in suggestions:
                st.info(s)

    # Saved strategies
    st.sidebar.subheader("Your Saved Strategies")
    saved = load_user_strategies(st.session_state.email)
    for s in saved:
        col_a, col_b = st.sidebar.columns([4,1])
        col_a.button(s["name"], key=f"load_{s['name']}", on_click=lambda y=s["yaml"]: st.session_state.update({"strategy_yaml": y}))
        col_b.button("🗑", key=f"del_{s['name']}", on_click=lambda n=s["name"]: delete_user_strategy(st.session_state.email, n))