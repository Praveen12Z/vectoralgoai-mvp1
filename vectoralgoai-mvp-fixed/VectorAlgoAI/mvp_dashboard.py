# mvp_dashboard.py
# VectorAlgoAI – Strategy Crash-Test MVP Dashboard
# (V2 with persistent results + Ruthless AI commentary + User Accounts
#  + Per-User Saved Strategies + Exports)

import traceback
from typing import Dict, Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.data_loader import load_ohlcv
from core.indicators import apply_all_indicators
from core.strategy_config import parse_strategy_yaml, StrategyConfig
from core.backtester_adapter import run_backtest_v2
from core.report import build_report  # reserved for future use
from core.auth import register_user, authenticate_user
from core.strategy_store import (
    load_user_strategies,
    save_user_strategy,
    delete_user_strategy,
)

# ---------------------------------------------------------------------
# Default strategy YAML
# ---------------------------------------------------------------------
DEFAULT_STRATEGY_YAML = """\
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


# ---------------------------------------------------------------------
# Ruthless AI commentary generator (A.1 Quant PM mode)
# ---------------------------------------------------------------------
def build_ruthless_ai_commentary(metrics: Dict[str, Any],
                                 trades_df: pd.DataFrame) -> str:
    """Return a markdown string with brutal strategy commentary."""
    grade = metrics.get("grade", "-")
    total_ret = float(metrics.get("total_return_pct", 0.0))
    pf = float(metrics.get("profit_factor", 0.0))
    win_rate = float(metrics.get("win_rate_pct", 0.0))
    num_trades = int(metrics.get("num_trades", 0))

    if "rr" in trades_df.columns and not trades_df["rr"].dropna().empty:
        avg_rr = float(trades_df["rr"].mean())
    else:
        avg_rr = None

    snapshot = (
        f"**Snapshot:** Grade **{grade}**, Total Return **{total_ret:.2f}%**, "
        f"Profit Factor **{pf:.2f}**, Win Rate **{win_rate:.2f}%**, Trades **{num_trades}**."
    )

    # High-level verdicts
    if pf >= 1.05 and total_ret > 0:
        verdict = (
            "This strategy is *barely* on the right side of zero, but it wouldn’t "
            "impress a serious PM yet. The edge is fragile and could vanish with a small regime shift."
        )
    elif 0.9 <= pf < 1.05:
        verdict = (
            "This wouldn’t survive a single allocation meeting. The edge is not just weak — "
            "it’s **non-existent**. PF around 1 is the market’s way of telling you it’s taking your money for sport."
        )
    else:
        verdict = (
            "This is not a drawdown, this is **structural failure**. "
            "The system is handing over PnL to the market on a consistent basis."
        )

    # Problems
    issues = []
    if pf < 1.0:
        issues.append("Strategy **loses money** (PF < 1). The market is charging you to participate.")
    elif pf < 1.1:
        issues.append("Profit factor is barely above 1 — any extra friction (slippage, spreads, fees) will erase it.")
    if win_rate < 45:
        issues.append("Win rate is **low (< 45%)**. You are relying heavily on big winners that rarely show up.")
    if num_trades < 20:
        issues.append("Sample size is **small**. Any conclusions are fragile and should be treated as a preview, not truth.")
    if avg_rr is not None and avg_rr <= 0:
        issues.append(
            f"Average RR is **{avg_rr:.2f}**, meaning you are structured to lose over time — "
            "you risk more on losers than you gain on winners."
        )

    if not issues:
        issues.append(
            "No single catastrophic metric, but nothing here screams *institutional-grade edge* either."
        )

    issues_md = "\n\n".join([f"• {txt}" for txt in issues])

    # Actionable next steps
    actions = [
        "Tighten stops relative to volatility (e.g. reduce ATR multiples) so losers get cut faster.",
        "Stretch take-profit levels slightly — stop asking the market for crumbs.",
        "Introduce a **regime filter** (trend vs chop, low vs high volatility) and *refuse to trade* in the wrong regime.",
        "Add additional confluence at entry instead of firing signals at every EMA touch.",
    ]
    if avg_rr is not None and avg_rr <= 0:
        actions.append(
            "Rebuild the entire RR structure: make sure your average winner is **meaningfully larger** than your average loser."
        )

    actions_md = "\n\n".join([f"• {txt}" for txt in actions])

    commentary = f"""
💀 **Ruthless Quant PM Review**

{snapshot}

The current configuration would **not** get capital at a professional desk. {verdict}

### Key Issues Detected
{issues_md}

### Non-Negotiable Next Steps
{actions_md}

**Final verdict:** Right now this is closer to a *donor account* than a trading strategy.  
Fix the structure, rebuild the risk/reward, and only then think about deploying real capital.
"""
    return commentary


# ---------------------------------------------------------------------
# MAIN DASHBOARD FUNCTION
# ---------------------------------------------------------------------
def run_mvp_dashboard():
    st.set_page_config(
        page_title="VectorAlgoAI – Strategy Crash-Test",
        layout="wide",
    )

    st.title("🧪 VectorAlgoAI – Strategy Crash-Test Lab (MVP)")

    # -----------------------------------------------------------------
    # AUTH BLOCK – LOGIN / REGISTER
    # -----------------------------------------------------------------
    if "user" not in st.session_state:
        st.session_state["user"] = None

    # If not logged in → show login/register screen and stop
    if st.session_state["user"] is None:
        st.markdown("#### 🔐 Please log in to access the Crash-Test Lab.")

        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input(
                "Password", type="password", key="login_password"
            )
            if st.button("Login", key="login_button"):
                ok, msg = authenticate_user(login_email, login_password)
                if ok:
                    st.session_state["user"] = login_email.strip().lower()
                    st.success("Login successful. Loading your lab...")
                    st.rerun()
                else:
                    st.error(msg)

        with tab_register:
            reg_email = st.text_input("Email", key="register_email")
            reg_pass1 = st.text_input(
                "Password", type="password", key="register_pass1"
            )
            reg_pass2 = st.text_input(
                "Confirm Password", type="password", key="register_pass2"
            )
            if st.button("Create Account", key="register_button"):
                ok, msg = register_user(reg_email, reg_pass1, reg_pass2)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

        return  # stop here if not logged in

    # Logged-in user
    user_email = st.session_state["user"]

    # -----------------------------------------------------------------
    # SIDEBAR ACCOUNT + SETTINGS
    # -----------------------------------------------------------------
    with st.sidebar:
        st.markdown("### 👤 Account")
        st.write(f"Logged in as **{user_email}**")
        if st.button("Logout"):
            st.session_state["user"] = None
            st.rerun()

        st.header("⚙️ Backtest Settings")
        years = st.slider("Years of history", 1, 15, 2)
        show_trade_lines = st.checkbox(
            "Show trade path lines (last 10 closed trades)", value=False
        )
        show_rr_labels = st.checkbox(
            "Show RR labels (last 10 closed trades)", value=False
        )
        st.write(
            "This controls how far back we pull candles from Massive/Polygon "
            "for the selected market & timeframe in your YAML."
        )
        st.info("Tip: Edit the YAML on the left, then click Run Crash-Test.")

    # -----------------------------------------------------------------
    # ENSURE SESSION KEYS FOR STRATEGY STATE
    # -----------------------------------------------------------------
    if "strategy_yaml" not in st.session_state:
        st.session_state["strategy_yaml"] = DEFAULT_STRATEGY_YAML
    if "current_strategy_name" not in st.session_state:
        st.session_state["current_strategy_name"] = ""

    # Load user strategies for this run
    user_strategies = load_user_strategies(user_email)

    # -----------------------------------------------------------------
    # MAIN LAYOUT: LEFT = Strategy & Saved Strategies, RIGHT = Run
    # -----------------------------------------------------------------
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📜 Strategy YAML")

        # Saved strategies selector
        saved_names = ["(none)"] + [s["name"] for s in user_strategies]
        selected_name = st.selectbox(
            "Saved strategies",
            options=saved_names,
            index=0,
            key="saved_strategy_select",
        )

        # Buttons for load/delete selected
        load_col, delete_col = st.columns(2)
        with load_col:
            if st.button("⬇️ Load Selected", use_container_width=True):
                if selected_name != "(none)":
                    match = next(
                        (s for s in user_strategies if s["name"] == selected_name),
                        None,
                    )
                    if match is not None:
                        st.session_state["strategy_yaml"] = match.get("yaml", "")
                        st.session_state["current_strategy_name"] = match.get("name", "")
                        st.success(f"Loaded strategy '{selected_name}'.")
                        st.rerun()
                    else:
                        st.warning("Selected strategy not found.")
                else:
                    st.info("Select a saved strategy first.")

        with delete_col:
            if st.button("🗑️ Delete Selected", use_container_width=True):
                if selected_name != "(none)":
                    ok, msg = delete_user_strategy(user_email, selected_name)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.info("Select a saved strategy to delete.")

        # Strategy name input
        st.text_input(
            "Strategy name (for saving)",
            key="current_strategy_name",
            placeholder="e.g. NAS100 Pullback v5",
        )

        # YAML editor
        st.text_area(
            "",
            height=400,
            key="strategy_yaml",
        )

        # Save / update current strategy
        if st.button("💾 Save / Update Strategy", use_container_width=True):
            name = st.session_state["current_strategy_name"]
            yaml_text = st.session_state["strategy_yaml"]
            ok, msg = save_user_strategy(user_email, name, yaml_text)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col2:
        st.subheader("")
        run_clicked = st.button("🔴 Run Crash-Test", use_container_width=True)

        if run_clicked:
            try:
                cfg: StrategyConfig = parse_strategy_yaml(
                    st.session_state["strategy_yaml"]
                )

                df_price = load_ohlcv(cfg.market, cfg.timeframe, years)
                if df_price is None or df_price.empty:
                    st.error("No price data loaded.")
                    st.session_state["bt_result"] = {
                        "error": "No price data loaded.",
                    }
                else:
                    df_feat = apply_all_indicators(df_price, cfg)
                    metrics, weaknesses, suggestions, trades_df = run_backtest_v2(
                        df_feat, cfg
                    )

                    st.session_state["bt_result"] = {
                        "cfg": cfg,
                        "df_feat": df_feat,
                        "metrics": metrics,
                        "weaknesses": weaknesses,
                        "suggestions": suggestions,
                        "trades_df": trades_df,
                        "data_range": (
                            df_price.index[0].date(),
                            df_price.index[-1].date(),
                            len(df_price),
                        ),
                    }

            except Exception as e:
                st.session_state["bt_result"] = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }

    # -----------------------------------------------------------------
    # READ RESULT FROM SESSION STATE
    # -----------------------------------------------------------------
    bt = st.session_state.get("bt_result", None)

    if bt is None:
        st.info("Run a Crash-Test to see charts and analytics.")
        return

    if "error" in bt:
        st.error("Error running backtest:")
        st.text(bt["error"])
        if "traceback" in bt:
            st.exception(bt["traceback"])
        return

    # Unpack stored objects
    cfg: StrategyConfig = bt["cfg"]
    df_feat: pd.DataFrame = bt["df_feat"]
    metrics = bt["metrics"]
    weaknesses = bt["weaknesses"]
    suggestions = bt["suggestions"]
    trades_df: pd.DataFrame = bt["trades_df"]
    data_start, data_end, data_bars = bt["data_range"]

    # -----------------------------------------------------------------
    # BASIC INFO
    # -----------------------------------------------------------------
    st.success(
        f"Parsed strategy: {cfg.name} · Market: {cfg.market} · Timeframe: {cfg.timeframe}"
    )
    st.info(
        f"Data Range Loaded: {data_start} → {data_end} · Bars: {data_bars}"
    )

    # -----------------------------------------------------------------
    # PRICE CHART WITH TRADES (GLOBAL VIEW)
    # -----------------------------------------------------------------
    st.subheader("📈 Price Chart with Trades")

    fig = go.Figure()

    # Candlesticks – thicker & clearer
    fig.add_trace(
        go.Candlestick(
            x=df_feat.index,
            open=df_feat["open"],
            high=df_feat["high"],
            low=df_feat["low"],
            close=df_feat["close"],
            name="Price",
            increasing_line_width=2,
            decreasing_line_width=2,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="rgba(38,166,154,0.65)",
            decreasing_fillcolor="rgba(239,83,80,0.65)",
        )
    )

    # EMA overlays
    for col, label in [("ema20", "EMA 20"), ("ema50", "EMA 50"), ("ema200", "EMA 200")]:
        if col in df_feat.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_feat.index,
                    y=df_feat[col],
                    mode="lines",
                    name=label,
                    line=dict(width=1.3),
                )
            )

    # ---- trades on main chart ----
    if not trades_df.empty:
        closed = trades_df.dropna(subset=["exit_time"]).copy()

        wins = closed[closed["pnl"] > 0]
        losses = closed[closed["pnl"] <= 0]

        win_long = wins[wins["direction"] == "long"]
        win_short = wins[wins["direction"] == "short"]
        loss_long = losses[losses["direction"] == "long"]
        loss_short = losses[losses["direction"] == "short"]

        entry_size = 9
        exit_size = 8

        # entry markers
        if not win_long.empty:
            fig.add_trace(
                go.Scatter(
                    x=win_long["entry_time"],
                    y=win_long["entry_price"],
                    mode="markers",
                    marker_symbol="triangle-up",
                    marker_size=entry_size,
                    marker_color="rgba(34,197,94,0.9)",
                    name="Long Entry (Win)",
                )
            )
        if not loss_long.empty:
            fig.add_trace(
                go.Scatter(
                    x=loss_long["entry_time"],
                    y=loss_long["entry_price"],
                    mode="markers",
                    marker_symbol="triangle-up",
                    marker_size=entry_size,
                    marker_color="rgba(248,113,113,0.95)",
                    name="Long Entry (Loss)",
                )
            )
        if not win_short.empty:
            fig.add_trace(
                go.Scatter(
                    x=win_short["entry_time"],
                    y=win_short["entry_price"],
                    mode="markers",
                    marker_symbol="triangle-down",
                    marker_size=entry_size,
                    marker_color="rgba(34,197,94,0.9)",
                    name="Short Entry (Win)",
                )
            )
        if not loss_short.empty:
            fig.add_trace(
                go.Scatter(
                    x=loss_short["entry_time"],
                    y=loss_short["entry_price"],
                    mode="markers",
                    marker_symbol="triangle-down",
                    marker_size=entry_size,
                    marker_color="rgba(248,113,113,0.95)",
                    name="Short Entry (Loss)",
                )
            )

        # exit markers
        if not wins.empty:
            fig.add_trace(
                go.Scatter(
                    x=wins["exit_time"],
                    y=wins["exit_price"],
                    mode="markers",
                    marker_symbol="x",
                    marker_size=exit_size,
                    marker_color="rgba(34,197,94,0.9)",
                    name="Exit (Win)",
                )
            )
        if not losses.empty:
            fig.add_trace(
                go.Scatter(
                    x=losses["exit_time"],
                    y=losses["exit_price"],
                    mode="markers",
                    marker_symbol="x",
                    marker_size=exit_size,
                    marker_color="rgba(248,113,113,0.95)",
                    name="Exit (Loss)",
                )
            )

        # optional path lines
        if show_trade_lines and not closed.empty:
            max_lines = 10
            closed_for_lines = closed.tail(max_lines)

            wins_for_lines = closed_for_lines[closed_for_lines["pnl"] > 0]
            losses_for_lines = closed_for_lines[closed_for_lines["pnl"] <= 0]

            added_win_line_legend = False
            added_loss_line_legend = False

            for _, row in wins_for_lines.iterrows():
                fig.add_trace(
                    go.Scatter(
                        x=[row["entry_time"], row["exit_time"]],
                        y=[row["entry_price"], row["exit_price"]],
                        mode="lines",
                        line=dict(color="rgba(34,197,94,0.7)", width=1.5),
                        name="Winning Trade" if not added_win_line_legend else "",
                        showlegend=not added_win_line_legend,
                    )
                )
                added_win_line_legend = True

            for _, row in losses_for_lines.iterrows():
                fig.add_trace(
                    go.Scatter(
                        x=[row["entry_time"], row["exit_time"]],
                        y=[row["entry_price"], row["exit_price"]],
                        mode="lines",
                        line=dict(color="rgba(248,113,113,0.75)", width=1.5),
                        name="Losing Trade" if not added_loss_line_legend else "",
                        showlegend=not added_loss_line_legend,
                    )
                )
                added_loss_line_legend = True

        # optional RR labels
        if show_rr_labels and not closed.empty and "rr" in closed.columns:
            max_labels = 10
            label_trades = closed.tail(max_labels).copy()
            texts = []
            for rr in label_trades["rr"]:
                if pd.isna(rr):
                    texts.append("")
                else:
                    sign = "+" if rr > 0 else ""
                    texts.append(f"RR {sign}{rr:.1f}")

            fig.add_trace(
                go.Scatter(
                    x=label_trades["exit_time"],
                    y=label_trades["exit_price"],
                    mode="text",
                    text=texts,
                    textposition="top center",
                    textfont=dict(size=9),
                    name="RR",
                    showlegend=False,
                )
            )

    # Layout tuned to look closer to a pro chart
    fig.update_layout(
        dragmode="pan",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,   # remove tiny second panel
        margin=dict(l=0, r=0, t=30, b=0),
        height=520,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(148,163,184,0.15)",
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148,163,184,0.15)",
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
        ),
        legend=dict(
            orientation="v",
            x=1.02,
            y=1,
            xanchor="left",
            bgcolor="rgba(15,23,42,0.85)",
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displaylogo": False,
            "doubleClick": "reset",
            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        },
    )

    # -----------------------------------------------------------------
    # STRATEGY DASHBOARD
    # -----------------------------------------------------------------
    st.subheader("📊 Strategy Dashboard")

    if trades_df.empty:
        st.info("No trades yet – run with more data or relax conditions.")
    else:
        total_trades = len(trades_df)
        wins_df = trades_df[trades_df["pnl"] > 0]
        losses_df = trades_df[trades_df["pnl"] <= 0]
        num_wins = len(wins_df)
        num_losses = len(losses_df)
        win_rate_calc = (num_wins / total_trades * 100.0) if total_trades > 0 else 0.0
        total_pnl = trades_df["pnl"].sum() if "pnl" in trades_df.columns else 0.0

        rr_available = "rr" in trades_df.columns
        avg_rr = trades_df["rr"].mean() if rr_available else None
        best_rr = trades_df["rr"].max() if rr_available else None
        worst_rr = trades_df["rr"].min() if rr_available else None

        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            st.markdown("**Trade Stats**")
            st.write(f"- Total trades: **{total_trades}**")
            st.write(f"- Wins: **{num_wins}**")
            st.write(f"- Losses: **{num_losses}**")
            st.write(f"- Win rate: **{win_rate_calc:.2f}%**")

        with col_s2:
            st.markdown("**Risk / Reward**")
            st.write(f"- Total PnL: **{total_pnl:.2f}**")
            if rr_available:
                st.write(f"- Avg RR: **{avg_rr:.2f}**")
                st.write(f"- Best RR: **{best_rr:.2f}**")
                st.write(f"- Worst RR: **{worst_rr:.2f}**")
            else:
                st.write("- RR data not available.")

        with col_s3:
            st.markdown("**RR Distribution**")
            if rr_available:
                st.bar_chart(trades_df["rr"])
            else:
                st.write("No RR column found in trade log.")

    # -----------------------------------------------------------------
    # TRADE INSPECTOR
    # -----------------------------------------------------------------
    if not trades_df.empty:
        st.subheader("🔍 Trade Inspector")

        closed_trades = trades_df.dropna(subset=["entry_time", "exit_time"]).copy()
        if closed_trades.empty:
            st.info("No closed trades to inspect yet.")
        else:
            closed_trades = closed_trades.sort_values("entry_time").reset_index(drop=True)

            def _fmt_trade(row):
                et = row["entry_time"]
                xt = row["exit_time"]
                dir_ = row["direction"]
                pnl = row.get("pnl", 0.0)
                rr = row.get("rr", None)
                et_str = str(et)[:16]
                xt_str = str(xt)[:16]
                base = f"{dir_.upper()} | {et_str} → {xt_str} | PnL {pnl:.2f}"
                if pd.notna(rr):
                    base += f" | RR {rr:.2f}"
                return base

            options = list(range(len(closed_trades)))
            labels = {i: _fmt_trade(closed_trades.iloc[i]) for i in options}

            selected_idx = st.selectbox(
                "Select a trade to inspect",
                options,
                format_func=lambda i: labels[i],
                key="trade_inspector_select",
            )

            trow = closed_trades.iloc[selected_idx]

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Direction**")
                st.write(str(trow["direction"]).upper())
                st.markdown("**Entry Time**")
                st.write(str(trow["entry_time"]))
                st.markdown("**Exit Time**")
                st.write(str(trow["exit_time"]))

            with c2:
                st.markdown("**Entry Price**")
                st.write(f"{trow['entry_price']:.4f}")
                st.markdown("**Exit Price**")
                st.write(f"{trow['exit_price']:.4f}")
                st.markdown("**PnL**")
                st.write(f"{trow['pnl']:.4f}")

            with c3:
                rr_val = trow["rr"] if "rr" in trow and pd.notna(trow["rr"]) else None
                st.markdown("**RR**")
                st.write(f"{rr_val:.2f}" if rr_val is not None else "N/A")

                # bars held
                try:
                    idx_entry = df_feat.index.get_indexer(
                        [trow["entry_time"]], method="nearest"
                    )[0]
                    idx_exit = df_feat.index.get_indexer(
                        [trow["exit_time"]], method="nearest"
                    )[0]
                    if idx_exit < idx_entry:
                        idx_entry, idx_exit = idx_exit, idx_entry
                    bars_held = idx_exit - idx_entry + 1
                except Exception:
                    bars_held = None

                st.markdown("**Bars in Trade**")
                st.write(bars_held if bars_held is not None else "N/A")
                st.markdown("**Approx Duration**")
                st.write(f"{bars_held} bars" if bars_held is not None else "N/A")

            # Trade zoom chart
            st.markdown("**Trade Zoom**")

            try:
                idx_entry = df_feat.index.get_indexer(
                    [trow["entry_time"]], method="nearest"
                )[0]
                idx_exit = df_feat.index.get_indexer(
                    [trow["exit_time"]], method="nearest"
                )[0]
                if idx_exit < idx_entry:
                    idx_entry, idx_exit = idx_exit, idx_entry

                pad = 20
                start_idx = max(0, idx_entry - pad)
                end_idx = min(len(df_feat) - 1, idx_exit + pad)
                df_window = df_feat.iloc[start_idx : end_idx + 1]

                fig_zoom = go.Figure()

                fig_zoom.add_trace(
                    go.Candlestick(
                        x=df_window.index,
                        open=df_window["open"],
                        high=df_window["high"],
                        low=df_window["low"],
                        close=df_window["close"],
                        name="Price",
                        increasing_line_width=2,
                        decreasing_line_width=2,
                        increasing_line_color="#26a69a",
                        decreasing_line_color="#ef5350",
                    )
                )

                for col, label in [
                    ("ema20", "EMA 20"),
                    ("ema50", "EMA 50"),
                    ("ema200", "EMA 200"),
                ]:
                    if col in df_window.columns:
                        fig_zoom.add_trace(
                            go.Scatter(
                                x=df_window.index,
                                y=df_window[col],
                                mode="lines",
                                name=label,
                                line=dict(width=1.3),
                            )
                        )

                fig_zoom.add_trace(
                    go.Scatter(
                        x=[trow["entry_time"]],
                        y=[trow["entry_price"]],
                        mode="markers",
                        marker_symbol="triangle-up"
                        if trow["direction"] == "long"
                        else "triangle-down",
                        marker_size=11,
                        marker_color="rgba(34,197,94,0.9)" if trow["pnl"] > 0 else "rgba(248,113,113,0.95)",
                        name="Trade Entry",
                    )
                )

                fig_zoom.add_trace(
                    go.Scatter(
                        x=[trow["exit_time"]],
                        y=[trow["exit_price"]],
                        mode="markers",
                        marker_symbol="x",
                        marker_size=10,
                        marker_color="rgba(34,197,94,0.9)" if trow["pnl"] > 0 else "rgba(248,113,113,0.95)",
                        name="Trade Exit",
                    )
                )

                fig_zoom.add_trace(
                    go.Scatter(
                        x=[trow["entry_time"], trow["exit_time"]],
                        y=[trow["entry_price"], trow["exit_price"]],
                        mode="lines",
                        line=dict(
                            color="rgba(34,197,94,0.85)" if trow["pnl"] > 0 else "rgba(248,113,113,0.9)",
                            width=1.8,
                        ),
                        name="Trade Path",
                    )
                )

                fig_zoom.update_layout(
                    dragmode="pan",
                    hovermode="x unified",
                    xaxis_rangeslider_visible=False,
                    margin=dict(l=0, r=0, t=30, b=0),
                    height=420,
                    xaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(148,163,184,0.15)",
                        showspikes=True,
                        spikemode="across",
                        spikesnap="cursor",
                        spikethickness=1,
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridcolor="rgba(148,163,184,0.15)",
                        showspikes=True,
                        spikemode="across",
                        spikesnap="cursor",
                        spikethickness=1,
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1,
                        bgcolor="rgba(15,23,42,0.85)",
                    ),
                )

                st.plotly_chart(
                    fig_zoom,
                    use_container_width=True,
                    config={
            "scrollZoom": True,
            "displaylogo": False,
            "doubleClick": "reset",
            "modeBarButtonsToRemove": ["select2d", "lasso2d"],
        },
                )
            except Exception as e:
                st.warning("Could not create zoomed trade chart.")
                st.text(str(e))

    # -----------------------------------------------------------------
    # TOP SUMMARY METRICS
    # -----------------------------------------------------------------
    st.subheader("Crash-Test Grade: " + metrics["grade"])
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Return", f"{metrics['total_return_pct']:.2f} %")
    m2.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
    m3.metric("Win Rate", f"{metrics['win_rate_pct']:.2f} %")
    m4.metric("Max Drawdown", f"{metrics['max_drawdown_pct']:.2f} %")
    m5.metric("Number of Trades", metrics["num_trades"])

    # -----------------------------------------------------------------
    # EQUITY CURVE
    # -----------------------------------------------------------------
    st.subheader("📉 Equity Curve")
    if metrics["num_trades"] == 0:
        st.info("No equity curve available (no closed trades).")
    else:
        st.line_chart(trades_df["pnl"].cumsum())

    # -----------------------------------------------------------------
    # TRADE LOG + EXPORTS + WEAKNESSES / SUGGESTIONS
    # -----------------------------------------------------------------
    st.subheader("📊 Trade Log")
    if trades_df.empty:
        st.warning("No trades generated by this strategy on the selected data.")
    else:
        st.dataframe(trades_df)

        st.markdown("#### ⬇️ Export")

        # Trades CSV
        csv_bytes = trades_df.to_csv(index=False).encode("utf-8")

        # build a safe filename from strategy name and market
        def _safe_name(txt: str) -> str:
            return "".join(
                c if c.isalnum() or c in ("-", "_") else "_"
                for c in txt.strip()
            ) or "strategy"

        base_name = _safe_name(cfg.name)
        market_tag = _safe_name(cfg.market)

        st.download_button(
            label="Download Trades CSV",
            data=csv_bytes,
            file_name=f"{base_name}_{market_tag}_trades.csv",
            mime="text/csv",
            use_container_width=True,
        )

        current_yaml = st.session_state.get("strategy_yaml", DEFAULT_STRATEGY_YAML)
        st.download_button(
            label="Download Strategy YAML",
            data=current_yaml.encode("utf-8"),
            file_name=f"{base_name}_{market_tag}.yaml",
            mime="text/yaml",
            use_container_width=True,
        )

    st.subheader("🔍 Strategy Weaknesses")
    if not weaknesses:
        st.write("- No major weaknesses detected (on this sample).")
    else:
        for w in weaknesses:
            st.write(f"- {w}")

    st.subheader("🧠 Suggestions for Improvement")
    if not suggestions:
        st.write("- No specific suggestions (try different parameters).")
    else:
        for s in suggestions:
            st.write(f"- {s}")

    # -----------------------------------------------------------------
    # RUTHLESS AI COMMENTARY BLOCK
    # -----------------------------------------------------------------
    st.subheader("💡 AI Commentary – Strategy Insights")
    commentary_text = build_ruthless_ai_commentary(metrics, trades_df)
    st.markdown(commentary_text)


# ---------------------------------------------------------------------
# Allow running directly
# ---------------------------------------------------------------------
if __name__ == "__main__":
    run_mvp_dashboard()
