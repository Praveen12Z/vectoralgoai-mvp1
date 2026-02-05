from dataclasses import dataclass
from typing import List, Dict, Any, Optional
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
    entry_long_conds = raw.get("entry", {}).get("long", [])
    entry_short_conds = raw.get("entry", {}).get("short", [])

    capital = float(raw["risk"].get("capital", 10000))
    risk_pct = float(raw["risk"].get("risk_per_trade_pct", 1.0)) / 100

    position = None
    trades = []
    equity = [capital]

    print("DEBUG: Entry long conditions:", entry_long_conds)   # ← debug

    for ts, row in df.iterrows():
        close = float(row["close"])
        equity.append(capital)

        # Exit
        if position:
            exit_hit = False
            if position.direction == "long":
                if position.sl and close <= position.sl: exit_hit = True
                elif position.tp and close >= position.tp: exit_hit = True
            else:
                if position.sl and close >= position.sl: exit_hit = True
                elif position.tp and close <= position.tp: exit_hit = True

            if exit_hit:
                pnl = (close - position.entry_price) * position.size if position.direction == "long" else \
                      (position.entry_price - close) * position.size
                trades.append({"pnl": pnl, "entry_time": position.entry_time, "exit_time": ts})
                capital += pnl
                position = None

        # Entry
        if not position:
            if _check_conditions(row, entry_long_conds):
                atr = row.get("atr14", (row["high"] - row["low"]) * 1.5)
                position = Position("long", ts, close, close - 2*atr, close + 3.5*atr, 1.0)
            elif _check_conditions(row, entry_short_conds):
                atr = row.get("atr14", (row["high"] - row["low"]) * 1.5)
                position = Position("short", ts, close, close + 2*atr, close - 3.5*atr, 1.0)

    trades_df = pd.DataFrame(trades)
    equity_series = pd.Series(equity, index=df.index[:len(equity)])

    if trades_df.empty:
        return {
            "metrics": {"total_return_pct": 0, "profit_factor": 0, "win_rate_pct": 0,
                        "max_drawdown_pct": 0, "num_trades": 0, "grade": "D"},
            "trades_df": pd.DataFrame(),
            "equity_series": equity_series
        }

    total_ret = float((equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0] * 100)
    pf = 1.5  # placeholder
    win_rate = 50
    max_dd = -15

    return {
        "metrics": {"total_return_pct": total_ret, "profit_factor": pf,
                    "win_rate_pct": win_rate, "max_drawdown_pct": max_dd,
                    "num_trades": len(trades_df), "grade": "C"},
        "trades_df": trades_df,
        "equity_series": equity_series
    }


def _check_conditions(row, conds):
    if not conds:
        return False
    for c in conds:
        left = row.get(c.get("left"), 0) if isinstance(c.get("left"), str) else c.get("left", 0)
        right = row.get(c.get("right"), 0) if isinstance(c.get("right"), str) else c.get("right", 0)
        op = c.get("op", "==")
        if op == ">" and left <= right: return False
        if op == "<" and left >= right: return False
        if op == ">=" and left < right: return False
        if op == "<=" and left > right: return False
        if op == "==" and left != right: return False
    return True
