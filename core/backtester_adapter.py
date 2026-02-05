from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np
import pandas as pd

from .strategy_config import StrategyConfig


@dataclass
class Position:
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    sl: float | None
    tp: float | None
    size: float


def run_backtest_v2(df: pd.DataFrame, cfg: StrategyConfig) -> Dict[str, Any]:
    raw = cfg.raw
    entry_long_conds = [c for c in raw.get("entry", {}).get("long", []) if "op" in c]
    entry_short_conds = [c for c in raw.get("entry", {}).get("short", []) if "op" in c]

    capital_start = float(raw["risk"].get("capital", 10000))
    risk_pct = float(raw["risk"].get("risk_per_trade_pct", 1.0)) / 100

    position: Position | None = None
    trades = []
    equity = [capital_start]

    for ts, row in df.iterrows():
        close = float(row["close"])

        # Exit check
        if position:
            exit_hit = False
            reason = ""
            if position.direction == "long":
                if position.sl is not None and close <= position.sl:
                    exit_hit = True
                    reason = "SL"
                elif position.tp is not None and close >= position.tp:
                    exit_hit = True
                    reason = "TP"
            else:  # short
                if position.sl is not None and close >= position.sl:
                    exit_hit = True
                    reason = "SL"
                elif position.tp is not None and close <= position.tp:
                    exit_hit = True
                    reason = "TP"

            if exit_hit:
                pnl = (close - position.entry_price) * position.size if position.direction == "long" else \
                      (position.entry_price - close) * position.size
                trades.append({
                    "entry_time": position.entry_time,
                    "exit_time": ts,
                    "direction": position.direction,
                    "entry_price": position.entry_price,
                    "exit_price": close,
                    "pnl": pnl,
                    "size": position.size,
                    "reason": reason
                })
                capital_start += pnl
                position = None

        # Entry check
        if not position:
            atr = row.get("atr14", (row["high"] - row["low"]) * 1.5)
            entered = False
            sl_val = tp_val = None
            direction = ""

            if any(_check_conditions(row, [c]) for c in [entry_long_conds]):
                direction = "long"
                entered = True
                sl_val = close - 2.0 * atr
                tp_val = close + 3.5 * atr
            elif any(_check_conditions(row, [c]) for c in [entry_short_conds]):
                direction = "short"
                entered = True
                sl_val = close + 2.0 * atr
                tp_val = close - 3.5 * atr

            if entered:
                risk_amount = capital_start * risk_pct
                risk_distance = abs(close - sl_val)
                size = risk_amount / risk_distance if risk_distance > 0 else 1.0

                position = Position(
                    direction=direction,
                    entry_time=ts,
                    entry_price=close,
                    sl=sl_val,
                    tp=tp_val,
                    size=size
                )

        equity.append(capital_start)

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return {
            "metrics": {"total_return_pct": 0, "profit_factor": 0, "win_rate_pct": 0,
                        "max_drawdown_pct": 0, "num_trades": 0, "grade": "D"},
            "trades_df": trades_df,
            "weaknesses": ["No trades generated."],
            "suggestions": ["Check entry conditions / data range."]
        }

    equity_series = pd.Series(equity, index=df.index[:len(equity)])
    peak = equity_series.cummax()
    dd = (equity_series - peak) / peak
    max_dd_pct = float(dd.min() * 100)

    gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)

    total_ret_pct = float((equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0] * 100)
    win_rate_pct = (trades_df["pnl"] > 0).mean() * 100 if len(trades_df) > 0 else 0
    num_trades = len(trades_df)

    grade = "A" if pf > 1.6 and abs(max_dd_pct) < 25 else \
            "B" if pf > 1.3 and abs(max_dd_pct) < 35 else \
            "C" if pf > 1.05 else "D"

    metrics = {
        "total_return_pct": total_ret_pct,
        "profit_factor": pf,
        "win_rate_pct": win_rate_pct,
        "max_drawdown_pct": max_dd_pct,
        "num_trades": num_trades,
        "grade": grade
    }

    weaknesses = []
    suggestions = []
    if num_trades < 20:
        weaknesses.append("Too few trades — statistically unreliable.")
        suggestions.append("Test on longer history or loosen filters.")
    if pf < 1.2:
        weaknesses.append("Profit factor too low.")
        suggestions.append("Improve reward:risk or filter bad entries.")

    return {
        "metrics": metrics,
        "trades_df": trades_df,
        "weaknesses": weaknesses,
        "suggestions": suggestions
    }


def _check_conditions(row, conds):
    for c in conds:
        left = row.get(c["left"], 0) if isinstance(c["left"], str) else c["left"]
        right = row.get(c["right"], 0) if isinstance(c["right"], str) else c["right"]
        op = c.get("op")
        if op == ">" and left <= right: return False
        if op == "<" and left >= right: return False
        if op == ">=" and left < right: return False
        if op == "<=" and left > right: return False
        if op == "==" and left != right: return False
    return True