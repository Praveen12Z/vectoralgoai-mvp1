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
    entry_regime: str = "unknown"


def run_backtest_v2(
    df: pd.DataFrame,
    cfg: StrategyConfig,
    slippage_pct: float = 0.0008,          # realistic slippage (0.08%)
    commission_per_trade: float = 3.0,     # fixed $ per trade
    monte_carlo_runs: int = 800            # default MC runs
) -> Dict[str, Any]:
    """
    V4 backtester:
    - Candle-by-candle execution
    - Slippage & commission simulation
    - Regime filter (ADX > 25 = trend only)
    - Monte Carlo robustness
    - Returns equity series, trades DF, MC results, regime stats
    """

    raw = cfg.raw
    entry_long_conds = raw.get("entry", {}).get("long", [])
    entry_short_conds = raw.get("entry", {}).get("short", [])
    exit_long_conds = raw.get("exit", {}).get("long", [])
    exit_short_conds = raw.get("exit", {}).get("short", [])

    capital_start = float(raw["risk"].get("capital", 10000))
    risk_pct = float(raw["risk"].get("risk_per_trade_pct", 1.0)) / 100

    position: Optional[Position] = None
    trades: List[Dict] = []
    equity = [capital_start]
    regimes = []  # track regime at each bar

    # ───── Regime detection (simple ADX proxy) ─────
    if "adx" not in df.columns:
        df["adx"] = 0  # fallback if not calculated
    df["regime"] = np.where(df["adx"] > 25, "trend", "chop")

    for ts, row in df.iterrows():
        close = float(row["close"])
        regime = row["regime"]

        regimes.append(regime)

        # ───── EXIT ─────
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
                # Apply slippage on exit
                exit_price = close * (1 - slippage_pct if position.direction == "long" else 1 + slippage_pct)
                pnl = (exit_price - position.entry_price) * position.size if position.direction == "long" else \
                      (position.entry_price - exit_price) * position.size
                pnl -= commission_per_trade  # fixed commission

                trades.append({
                    "entry_time": position.entry_time,
                    "exit_time": ts,
                    "direction": position.direction,
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "size": position.size,
                    "reason": reason,
                    "regime": position.entry_regime
                })
                capital_start += pnl
                position = None

        # ───── ENTRY ───── (only in trend regime)
        if not position and regime == "trend":
            entered = False
            sl_val = tp_val = None
            direction = ""

            if _check_conditions(row, entry_long_conds):
                direction = "long"
                entered = True
                atr = row.get("atr14", (row["high"] - row["low"]) * 1.5)
                sl_val = close - 2.0 * atr
                tp_val = close + 3.5 * atr

            elif _check_conditions(row, entry_short_conds):
                direction = "short"
                entered = True
                atr = row.get("atr14", (row["high"] - row["low"]) * 1.5)
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
                    size=size,
                    entry_regime=regime
                )

        equity.append(capital_start)

    # ───── Build results ─────
    trades_df = pd.DataFrame(trades)
    equity_series = pd.Series(equity, index=df.index[:len(equity)])

    if trades_df.empty:
        return {
            "metrics": {
                "total_return_pct": 0.0,
                "profit_factor": 0.0,
                "win_rate_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "num_trades": 0,
                "grade": "D"
            },
            "trades_df": pd.DataFrame(),
            "equity_series": equity_series,
            "monte_carlo": {},
            "regime_stats": {}
        }

    # Core metrics
    peak = equity_series.cummax()
    dd = (equity_series - peak) / peak
    max_dd_pct = float(dd.min() * 100)

    gross_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0)

    total_ret_pct = float((equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0] * 100)
    win_rate_pct = (trades_df["pnl"] > 0).mean() * 100 if len(trades_df) > 0 else 0

    grade = "A" if pf > 1.8 and abs(max_dd_pct) < 20 else \
            "B" if pf > 1.3 and abs(max_dd_pct) < 35 else \
            "C" if pf > 1.0 else "D"

    metrics = {
        "total_return_pct": total_ret_pct,
        "profit_factor": pf,
        "win_rate_pct": win_rate_pct,
        "max_drawdown_pct": max_dd_pct,
        "num_trades": len(trades_df),
        "grade": grade
    }

    # ───── MONTE CARLO ─────
    monte_carlo = {}
    if monte_carlo_runs > 0 and not trades_df.empty:
        returns = trades_df["pnl"] / capital_start  # normalized returns
        mc_returns = []
        for _ in range(monte_carlo_runs):
            shuffled = returns.sample(frac=1, replace=True).values
            noise = np.random.normal(0, 0.0005, len(shuffled))  # extra realism
            sim_path = np.cumprod(1 + shuffled + noise) - 1
            mc_returns.append(sim_path[-1] * 100)
        monte_carlo = {
            "mean_return": np.mean(mc_returns),
            "median_return": np.median(mc_returns),
            "worst_5pct": np.percentile(mc_returns, 5),
            "best_5pct": np.percentile(mc_returns, 95),
            "runs": monte_carlo_runs
        }

    # ───── REGIME STATS ─────
    regime_stats = trades_df.groupby("regime")["pnl"].agg(["sum", "count", "mean", "std"]).round(2).to_dict()

    return {
        "metrics": metrics,
        "trades_df": trades_df,
        "equity_series": equity_series,
        "monte_carlo": monte_carlo,
        "regime_stats": regime_stats
    }


def _check_conditions(row: pd.Series, conds: List[Dict]) -> bool:
    if not conds:
        return False
    for c in conds:
        left = row.get(c["left"], 0) if isinstance(c["left"], str) else c["left"]
        right = row.get(c["right"], 0) if isinstance(c["right"], str) else c["right"]
        op = c.get("op", "==")
        if op == ">" and left <= right: return False
        if op == "<" and left >= right: return False
        if op == ">=" and left < right: return False
        if op == "<=" and left > right: return False
        if op == "==" and left != right: return False
    return True
