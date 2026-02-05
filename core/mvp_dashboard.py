import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from .data_loader import load_ohlcv
from .indicators import apply_all_indicators
from .strategy_config import parse_strategy_yaml
from .backtester_adapter import run_backtest_v2
from .strategy_store import load_user_strategies, save_user_strategy, delete_user_strategy
from .auth import authenticate_user, register_user

# Default strategy (kept for convenience)
DEFAULT_YAML = """name: "NAS100 Momentum Pullback"
market: "NAS100"
timeframe: "1h"

indicators:
  - name: ema20
    type: ema
    period: 20
  - name: ema50
    type: ema
    period: 50
  - name: ema200
    type: ema
    period: 200
  - name: rsi14
    type: rsi
    period: 14
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
    - left: rsi14
      op: "<"
      right: 55

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
    - left: rsi14
      op: ">"
      right: 45

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

    # ====================== AUTH ======================
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

    # ====================== SIDEBAR ======================
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state.email}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        st.header("Market & Settings")
        available_markets = [
            "NAS100", "US30", "SPX500",
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
            "EURJPY", "GBPJPY",
            "XAUUSD", "XAGUSD"
        ]
        market = st.selectbox("Market", available_markets, index=0)
        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)
        years = st.slider("Years of history", 0.1, 10.0, 1.0, step=0.1)

        st.info("Note: Free Polygon tier has rate limits. Wait 5–10 min between heavy tests.")

    # ====================== MAIN UI ======================
    strategy_yaml = st.text_area("Strategy YAML", DEFAULT_YAML, height=380)

    if st.button("Run Crash-Test", type="primary", use_container_width=True):
        with st.spinner("Loading market data..."):
            df = load_ohlcv(market, timeframe, years)
            if df.empty:
                st.stop()

        with st.spinner("Applying indicators & running backtest..."):
            try:
                cfg = parse_strategy_yaml(strategy_yaml)
                df = apply_all_indicators(df, cfg)
                result = run_backtest_v2(df, cfg)
                metrics = result["metrics"]
                trades_df = result["trades_df"]
                weaknesses = result["weaknesses"]
                suggestions = result["suggestions"]
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.stop()

        # Show results
        st.success(f"Backtest complete on {market} | {timeframe} | {len(df)} bars")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Return", f"{metrics['total_return_pct']:.2f}%")
        col2.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        col3.metric("Win Rate", f"{metrics['win_rate_pct']:.1f}%")
        col4.metric("Max DD", f"{metrics['max_drawdown_pct']:.1f}%")
        col5.metric("Trades", metrics["num_trades"])

        st.subheader("Equity Curve")
        if not trades_df.empty:
            equity = trades_df["pnl"].cumsum() + 10000
            st.line_chart(equity)

        st.subheader("Trade Log")
        st.dataframe(trades_df)

        st.subheader("Weaknesses & Suggestions")
        for w in weaknesses:
            st.warning(w)
        for s in suggestions:
            st.info(s)

    # Optional: Save strategy button (kept simple)
    if st.button("💾 Save Strategy"):
        name = st.text_input("Strategy name", "My Strategy")
        ok, msg = save_user_strategy(st.session_state.email, name, strategy_yaml)
        st.success(msg) if ok else st.error(msg)
