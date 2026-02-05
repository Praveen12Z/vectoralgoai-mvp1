# core/backtester_adapter.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .strategy_config import StrategyConfig


@dataclass
class Position:
    direction: str          # "long" or "short"
    entry_time: pd.Timestamp
    entry_price: float
    sl: float | None
    tp: float | None
    risk_per_unit: float | None  # distance to stop (for RR)
    

def _get_val(row: pd.Series, token):
    if isinstance(token, (int, float)):
        return float(token)
    if isinstance(token, str):
        try:
            return float(token)
        except ValueError:
            return float(row[token])
    return float(token)


def _check_conditions(row: pd.Series, conds: List[Dict]) -> bool:
    if not conds:
        return False
    for c in conds:
        left = _get_val(row, c.get("left"))
        right = _get_val(row, c.get("right"))
        op = c.get("op", "==")
        if op == ">":
            ok = left > right
        elif op == "<":
            ok = left < right
        elif op == ">=":
            ok = left >= right
        elif op == "<=":
            ok = left <= right
        elif op == "==":
            ok = left == right
        else:
            ok = False
        if not ok:
            return False
    return True


def _build_exits(row: pd.Series, cfg: StrategyConfig, side: str) -> Tuple[float | None, float | None, float | None]:
    """
    Return (sl, tp, risk_per_unit) for the given side based on ATR rules.
    """
    exit_rules = (cfg.raw.get("exit", {}) or {}).get(side, []) or []
    atr_val = None
    entry_price = row["close"]
    sl = tp = None

    for rule in exit_rules:
        if rule.get("type") in ("atr_sl", "atr_tp"):
            atr_col = rule.get("atr_col")
            mult = float(rule.get("multiple", 2.0))
            if atr_col in row.index:
                atr_val = float(row[atr_col])
            else:
                continue

            if rule["type"] == "atr_sl":
                if side == "long":
                    sl = entry_price - mult * atr_val
                else:
                    sl = entry_price + mult * atr_val
            elif rule["type"] == "atr_tp":
                if side == "long":
                    tp = entry_price + mult * atr_val
                else:
                    tp = entry_price - mult * atr_val

    risk_per_unit = None
    if sl is not None:
        if side == "long":
            risk_per_unit = entry_price - sl
        else:
            risk_per_unit = sl - entry_price

    return sl, tp, risk_per_unit


def _grade_strategy(total_ret: float, pf: float, win_rate: float, num_trades: int) -> str:
    if num_trades < 10:
        return "D"
    if pf > 1.6 and total_ret > 15 and win_rate > 50:
        return "A"
    if pf > 1.3 and total_ret > 5:
        return "B"
    if pf > 1.05:
        return "C"
    return "D"


def run_backtest_v2(df: pd.DataFrame, cfg: StrategyConfig):
    """
    Very simple bar-by-bar backtester using YAML conditions.
    - Only supports one open position at a time.
    - Uses close price for entry/exit.
    """
    raw = cfg.raw or {}
    entry_block = raw.get("entry", {}) or {}

    long_conds = entry_block.get("long", []) or []
    short_conds = entry_block.get("short", []) or []

    risk_cfg = raw.get("risk", {}) or {}
    capital = float(risk_cfg.get("capital", 10000.0))

    position: Position | None = None
    trades: List[Dict] = []

    for ts, row in df.iterrows():
        # close existing position?
        if position is not None:
            price = float(row["close"])
            exit_reason = None

            if position.direction == "long":
                if position.sl is not None and price <= position.sl:
                    exit_reason = "SL"
                if position.tp is not None and price >= position.tp:
                    exit_reason = "TP"
            else:  # short
                if position.sl is not None and price >= position.sl:
                    exit_reason = "SL"
                if position.tp is not None and price <= position.tp:
                    exit_reason = "TP"

            # simple time-based fail-safe: close at last bar
            is_last_bar = ts == df.index[-1]

            if exit_reason is not None or is_last_bar:
                exit_price = price
                if position.direction == "long":
                    pnl_per_unit = exit_price - position.entry_price
                else:
                    pnl_per_unit = position.entry_price - exit_price

                risk = position.risk_per_unit or max(abs(pnl_per_unit), 1e-8)
                rr = pnl_per_unit / risk

                trades.append(
                    {
                        "entry_time": position.entry_time,
                        "exit_time": ts,
                        "direction": position.direction,
                        "entry_price": position.entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl_per_unit,
                        "rr": rr,
                        "exit_reason": exit_reason or "time_exit",
                    }
                )
                position = None

                # after closing, continue to next loop iteration to allow re-entry
                continue

        # if flat, check for entries
        if position is None:
            if _check_conditions(row, long_conds):
                sl, tp, risk_per_unit = _build_exits(row, cfg, "long")
                position = Position(
                    direction="long",
                    entry_time=ts,
                    entry_price=float(row["close"]),
                    sl=sl,
                    tp=tp,
                    risk_per_unit=risk_per_unit,
                )
            elif _check_conditions(row, short_conds):
                sl, tp, risk_per_unit = _build_exits(row, cfg, "short")
                position = Position(
                    direction="short",
                    entry_time=ts,
                    entry_price=float(row["close"]),
                    sl=sl,
                    tp=tp,
                    risk_per_unit=risk_per_unit,
                )

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        metrics = {
            "total_return_pct": 0.0,
            "profit_factor": 0.0,
            "win_rate_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "num_trades": 0,
            "grade": "D",
        }
        weaknesses = ["Too few trades to evaluate.", "Strategy might be over-filtered."]
        suggestions = ["Relax entry conditions or test on more data."]
        return metrics, weaknesses, suggestions, trades_df

    # equity & metrics
    pnl = trades_df["pnl"].values
    equity = capital + np.cumsum(pnl)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd_pct = float(dd.min() * 100.0)

    gross_profit = trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()
    gross_loss = -trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum()
    if gross_loss <= 0:
        pf = float("inf") if gross_profit > 0 else 0.0
    else:
        pf = float(gross_profit / gross_loss)

    total_return_pct = float((equity[-1] - capital) / capital * 100.0)
    num_trades = len(trades_df)
    win_rate_pct = float((trades_df["pnl"] > 0).mean() * 100.0)

    grade = _grade_strategy(total_return_pct, pf, win_rate_pct, num_trades)

    metrics = {
        "total_return_pct": total_return_pct,
        "profit_factor": pf,
        "win_rate_pct": win_rate_pct,
        "max_drawdown_pct": max_dd_pct,
        "num_trades": num_trades,
        "grade": grade,
    }

    weaknesses: List[str] = []
    suggestions: List[str] = []

    if num_trades < 20:
        weaknesses.append("Too few trades to determine stability (sample < 20).")
        suggestions.append("Test on more history or trade more frequently.")
    if pf < 1.0:
        weaknesses.append("Profit factor below 1 – strategy loses money net of costs.")
        suggestions.append("Rebuild RR structure; aim for PF > 1.3 on robust samples.")
    if win_rate_pct < 45:
        weaknesses.append("Win rate is low (< 45%).")
        suggestions.append("Improve confluence at entry and tighten stops.")
    if max_dd_pct < -20:
        weaknesses.append("Max drawdown deeper than -20%.")
        suggestions.append("Reduce risk per trade or add volatility filters.")

    return metrics, weaknesses, suggestions, trades_df
