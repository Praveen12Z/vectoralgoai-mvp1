# core/report.py

"""
This version matches the ORIGINAL MVP interface:

build_report(bt_result, cfg) → 
    returns: (metrics, weaknesses, suggestions, trades_df)

Fully compatible with mvp_dashboard.py.
"""

def _build_weaknesses(m):
    w = []

    if m.get("num_trades", 0) < 20:
        w.append("Too few trades to evaluate reliability.")

    if m.get("profit_factor", 0) < 1:
        w.append("Losing strategy (Profit Factor < 1).")

    if m.get("win_rate_pct", 0) < 45:
        w.append("Low win rate (< 45%).")

    if m.get("max_drawdown_pct", 0) < -25:
        w.append("High drawdown (> 25%).")

    return w


def _build_suggestions(m):
    s = []

    if m.get("profit_factor", 0) < 1.2:
        s.append("Improve exits or risk management to raise profit factor.")

    if m.get("win_rate_pct", 0) < 45:
        s.append("Add more confluence filters to entry logic.")

    if m.get("num_trades", 0) < 20:
        s.append("Increase sample size: test more bars or relax rules.")

    if m.get("max_drawdown_pct", 0) < -25:
        s.append("Reduce position sizing or filter out choppy markets.")

    return s


def _format_report_text(metrics, weaknesses, suggestions):
    """
    This is optional helper for UI.
    """
    lines = []
    lines.append("📊 Strategy Performance Report")
    lines.append("----------------------------------")
    lines.append(f"Grade: {metrics.get('grade')}")
    lines.append(f"Win Rate: {metrics.get('win_rate_pct'):.2f}%")
    lines.append(f"Profit Factor: {metrics.get('profit_factor'):.2f}")
    lines.append(f"Total Return: {metrics.get('total_return_pct'):.2f}%")
    lines.append(f"Max Drawdown: {metrics.get('max_drawdown_pct'):.2f}%")
    lines.append(f"Number of Trades: {metrics.get('num_trades')}")
    lines.append("")

    lines.append("Weaknesses:")
    for w in weaknesses:
        lines.append(f"- {w}")
    lines.append("")

    lines.append("Suggestions:")
    for s in suggestions:
        lines.append(f"- {s}")
    lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------
# MAIN INTERFACE – MUST MATCH MVP EXPECTATION
# --------------------------------------------------------
def build_report(bt_result: dict, cfg):
    """
    bt_result = output of run_backtest() 
    cfg = StrategyConfig (unused for now, but kept for compatibility)

    RETURNS → (metrics, weaknesses, suggestions, trades_df)
    """
    metrics = bt_result["metrics"]
    trades_df = bt_result["trades"]

    weaknesses = _build_weaknesses(metrics)
    suggestions = _build_suggestions(metrics)

    return metrics, weaknesses, suggestions, trades_df
