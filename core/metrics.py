# core/metrics.py

import numpy as np
import pandas as pd


# ---------------------------------------------------------------
# Helper: maximum drawdown
# ---------------------------------------------------------------
def max_drawdown(equity: pd.Series) -> float:
    """
    Returns max drawdown as a negative percentage.
    """
    if equity.empty:
        return 0.0

    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min() * 100)


# ---------------------------------------------------------------
# Helper: profit factor
# ---------------------------------------------------------------
def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    wins = trades[trades["pnl"] > 0]["pnl"].sum()
    losses = trades[trades["pnl"] < 0]["pnl"].abs().sum()
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


# ---------------------------------------------------------------
# Helper: win rate
# ---------------------------------------------------------------
def win_rate(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    wins = len(trades[trades["pnl"] > 0])
    total = len(trades)
    return float((wins / total) * 100)


# ---------------------------------------------------------------
# Helper: average RR per trade
# ---------------------------------------------------------------
def avg_rr(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    return float(trades["rr"].replace([np.inf, -np.inf], np.nan).dropna().mean())


# ---------------------------------------------------------------
# MAIN METRICS ENGINE
# ---------------------------------------------------------------
def compute_metrics(equity: pd.Series, trades: pd.DataFrame, starting_capital: float):
    """
    Returns metrics dict expected by your dashboard.
    """

    if equity.empty:
        return {
            "grade": "D",
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "profit_factor": 0.0,
            "win_rate_pct": 0.0,
            "avg_rr_per_trade": 0.0,
            "num_trades": 0,
            "capital_tested": starting_capital,
        }

    final_capital = equity.iloc[-1]
    total_return_pct = float((final_capital / starting_capital - 1) * 100)

    md = max_drawdown(equity)
    pf = profit_factor(trades)
    wr = win_rate(trades)
    rr = avg_rr(trades)
    num = int(len(trades))

    # Simple SaaS-grade grading logic:
    if pf > 1.8 and md > -20:
        grade = "A"
    elif pf > 1.3 and md > -30:
        grade = "B"
    elif pf > 1.0:
        grade = "C"
    else:
        grade = "D"

    return {
        "grade": grade,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": md,
        "profit_factor": pf,
        "win_rate_pct": wr,
        "avg_rr_per_trade": rr,
        "num_trades": num,
        "capital_tested": starting_capital,
    }
