# core/backtester.py
import pandas as pd
from typing import Dict, Callable, List


# ===============================================================
# RULE PARSING
# ===============================================================
def _resolve_rule_type(rule_obj) -> str:
    op = getattr(rule_obj, "op", None)
    if op in (">", "<", ">=", "<=", "==", "!="):
        return op
    if op in ("cross", "crossover"):
        return "crossover"
    if op in ("crossunder",):
        return "crossunder"
    return "unknown"


def _parse_entry_rules(rules: List[object]) -> List[Callable[[pd.DataFrame], bool]]:
    parsed = []

    for rule in rules:
        left = rule.left
        right = rule.right
        rtype = _resolve_rule_type(rule)

        if rtype == ">":
            parsed.append(lambda df, l=left, r=right: df[l].iloc[-1] > df[r].iloc[-1])
        elif rtype == "<":
            parsed.append(lambda df, l=left, r=right: df[l].iloc[-1] < df[r].iloc[-1])

        elif rtype == "crossover":
            parsed.append(
                lambda df, l=left, r=right:
                df[l].iloc[-2] < df[r].iloc[-2] and df[l].iloc[-1] > df[r].iloc[-1]
            )

        elif rtype == "crossunder":
            parsed.append(
                lambda df, l=left, r=right:
                df[l].iloc[-2] > df[r].iloc[-2] and df[l].iloc[-1] < df[r].iloc[-1]
            )

    return parsed


def _parse_exit_rules(rules: List[object]) -> List[Callable[[pd.DataFrame], bool]]:
    parsed = []

    for rule in rules:
        # ATR exits have no left/right → skip for now (MVP safe mode)
        if not hasattr(rule, "left") or not hasattr(rule, "right"):
            continue

        left = rule.left
        right = rule.right
        rtype = _resolve_rule_type(rule)

        if rtype == ">":
            parsed.append(lambda df, l=left, r=right: df[l].iloc[-1] > df[r].iloc[-1])

        elif rtype == "<":
            parsed.append(lambda df, l=left, r=right: df[l].iloc[-1] < df[r].iloc[-1])

        elif rtype == "crossover":
            parsed.append(
                lambda df, l=left, r=right:
                df[l].iloc[-2] < df[r].iloc[-2] and df[l].iloc[-1] > df[r].iloc[-1]
            )

        elif rtype == "crossunder":
            parsed.append(
                lambda df, l=left, r=right:
                df[l].iloc[-2] > df[r].iloc[-2] and df[l].iloc[-1] < df[r].iloc[-1]
            )

    return parsed


# ===============================================================
# METRICS
# ===============================================================
def _compute_metrics(equity: pd.Series, trades: pd.DataFrame, capital: float):
    if equity.empty:
        return {
            "grade": "Incomplete",
            "win_rate_pct": 0,
            "profit_factor": 0,
            "max_drawdown_pct": 0,
            "total_return_pct": 0,
            "avg_rr_per_trade": 0,
            "capital_tested": capital,
            "num_trades": 0,
        }

    final_eq = equity.iloc[-1]
    total_return_pct = (final_eq / capital - 1) * 100

    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd_pct = float(dd.min() * 100)

    if trades.empty:
        return {
            "grade": "D",
            "win_rate_pct": 0,
            "profit_factor": 0,
            "max_drawdown_pct": max_dd_pct,
            "total_return_pct": total_return_pct,
            "avg_rr_per_trade": 0,
            "capital_tested": capital,
            "num_trades": 0,
        }

    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] < 0]

    num = len(trades)
    win_rate = len(wins) / num * 100
    gross_profit = wins["pnl"].sum()
    gross_loss = losses["pnl"].abs().sum()
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    avg_rr = trades["rr"].mean()

    grade = "A" if pf > 1.5 and max_dd_pct > -15 else "B"

    return {
        "grade": grade,
        "win_rate_pct": win_rate,
        "profit_factor": pf,
        "max_drawdown_pct": max_dd_pct,
        "total_return_pct": total_return_pct,
        "avg_rr_per_trade": avg_rr,
        "capital_tested": capital,
        "num_trades": num,
    }


# ===============================================================
# MAIN BACKTEST ENGINE (MVP simple version)
# ===============================================================
def run_backtest(df: pd.DataFrame, cfg) -> Dict:
    """
    Simplified MVP backtester:
    - buys when ANY entry rule true
    - exits when ANY exit rule true
    - no ATR exits yet (ignored safely)
    """
    df = df.copy()
    capital = cfg.risk.capital
    entry_rules = _parse_entry_rules(cfg.entry.long)
    exit_rules = _parse_exit_rules(cfg.exit.long)

    position = 0
    entry_price = 0

    trades = []

    equity = []

    eq = capital

    for i in range(2, len(df)):
        window = df.iloc[: i + 1]

        # exit first
        if position == 1 and any(rule(window) for rule in exit_rules):
            pnl = window["close"].iloc[-1] - entry_price
            rr = pnl / (entry_price * cfg.risk.risk_per_trade_pct / 100)

            trades.append({"entry": entry_price, "exit": window["close"].iloc[-1], "pnl": pnl, "rr": rr})
            eq += pnl
            position = 0

        # entry
        if position == 0 and any(rule(window) for rule in entry_rules):
            entry_price = window["close"].iloc[-1]
            position = 1

        equity.append(eq)

    equity_series = pd.Series(equity, index=df.index[2:])
    trades_df = pd.DataFrame(trades)

    metrics = _compute_metrics(equity_series, trades_df, capital)

    return {
        "metrics": metrics,
        "equity_curve": equity_series,
        "trades": trades_df,
    }
