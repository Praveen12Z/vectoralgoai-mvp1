# core/backtester_pro_engine.py

"""
PROFESSIONAL BACKTEST ENGINE — VectorAlgoAI v2

This engine supports:
 - Candle-by-candle execution
 - Long / Short / Flat states
 - Entry on next-candle open
 - Exit on next-candle open
 - ATR-based SL / TP
 - Risk-per-trade sizing
 - Trade log construction
 - Equity curve
 - Multi-condition rule evaluation
"""

import pandas as pd
from core.rule_engine import (
    check_entry_long,
    check_entry_short,
    check_exit_long,
    check_exit_short,
)


# -------------------------------------------------------------
# Trade object
# -------------------------------------------------------------
class Trade:
    def __init__(self, direction, entry_idx, entry_price, size):
        self.direction = direction      # "long" or "short"
        self.entry_idx = entry_idx
        self.entry_price = entry_price
        self.size = size                # number of units
        self.exit_idx = None
        self.exit_price = None
        self.pnl = 0
        self.rr = 0
        self.reason = None              # SL, TP, exit rule


# -------------------------------------------------------------
# Main engine
# -------------------------------------------------------------
def run_backtest_pro(df: pd.DataFrame, cfg):
    df = df.copy()
    capital = cfg.risk.capital
    risk_pct = cfg.risk.risk_per_trade_pct / 100

    position = None      # None, or Trade(...)
    equity = []
    trades = []

    for i in range(50, len(df) - 1):
        row = df.iloc[i]
        next_row = df.iloc[i + 1]

        # -----------------------------------------------------
        # 1) EXIT LOGIC
        # -----------------------------------------------------
        if position is not None:
            if position.direction == "long":
                sl = row.get("sl", None)
                tp = row.get("tp", None)

                # exit via SL
                if sl and row["low"] <= sl <= row["high"]:
                    position.exit_idx = i + 1
                    position.exit_price = next_row["open"]
                    position.reason = "SL hit"
                # exit via TP
                elif tp and row["low"] <= tp <= row["high"]:
                    position.exit_idx = i + 1
                    position.exit_price = next_row["open"]
                    position.reason = "TP hit"
                # exit via rule
                elif check_exit_long(df, i, cfg.exit) and position.direction == "long":
                    position.exit_idx = i + 1
                    position.exit_price = next_row["open"]
                    position.reason = "Exit rule"

            elif position.direction == "short":
                sl = row.get("sl", None)
                tp = row.get("tp", None)
                if sl and row["low"] <= sl <= row["high"]:
                    position.exit_idx = i + 1
                    position.exit_price = next_row["open"]
                    position.reason = "SL hit"
                elif tp and row["low"] <= tp <= row["high"]:
                    position.exit_idx = i + 1
                    position.exit_price = next_row["open"]
                    position.reason = "TP hit"
                elif check_exit_short(df, i, cfg.exit):
                    position.exit_idx = i + 1
                    position.exit_price = next_row["open"]
                    position.reason = "Exit rule"

            # Close if exit found
            if position.exit_idx is not None:
                if position.direction == "long":
                    position.pnl = (position.exit_price - position.entry_price) * position.size
                else:
                    position.pnl = (position.entry_price - position.exit_price) * position.size

                if position.entry_price != 0:
                    position.rr = position.pnl / (abs(position.entry_price * risk_pct))

                trades.append(position)
                capital += position.pnl
                position = None

        # -----------------------------------------------------
        # 2) ENTRY LOGIC
        # -----------------------------------------------------
        if position is None:
            if check_entry_long(df, i, cfg.entry):
                entry_price = next_row["open"]
                risk_amount = capital * risk_pct

                atr_col = None
                for ind in cfg.indicators:
                    if "atr" in ind.type:
                        atr_col = ind.name

                atr_val = row.get(atr_col, None)
                if atr_val and atr_val > 0:
                    stop = entry_price - 2 * atr_val   # default SL
                    size = risk_amount / (entry_price - stop)
                else:
                    size = risk_amount / entry_price

                t = Trade("long", i + 1, entry_price, size)
                position = t

            elif check_entry_short(df, i, cfg.entry):
                entry_price = next_row["open"]
                risk_amount = capital * risk_pct

                atr_col = None
                for ind in cfg.indicators:
                    if "atr" in ind.type:
                        atr_col = ind.name

                atr_val = row.get(atr_col, None)
                if atr_val and atr_val > 0:
                    stop = entry_price + 2 * atr_val
                    size = risk_amount / (stop - entry_price)
                else:
                    size = risk_amount / entry_price

                t = Trade("short", i + 1, entry_price, size)
                position = t

        equity.append(capital)

    equity_series = pd.Series(equity, index=df.index[50 : len(df) - 1])

    # build trades DataFrame
    trades_df = pd.DataFrame(
        [
            {
                "direction": t.direction,
                "entry_time": df.index[t.entry_idx],
                "exit_time": df.index[t.exit_idx] if t.exit_idx else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "rr": t.rr,
                "reason": t.reason,
            }
            for t in trades
        ]
    )

    return {
        "equity": equity_series,
        "trades": trades_df,
        "final_capital": capital,
    }
