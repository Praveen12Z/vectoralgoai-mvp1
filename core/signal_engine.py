# core/signal_engine.py
from typing import Dict, Any

import pandas as pd

from .indicators import apply_indicators
from .rules import evaluate_rule_group


def generate_signals(price_df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """
    price_df: DataFrame with at least ['open', 'high', 'low', 'close']
    config: loaded YAML
    Adds columns:
      - all defined indicators
      - 'entry_signal' (1 for buy, 0 otherwise)
      - 'exit_signal' (1 for exit, 0 otherwise)
      - 'position' (+1 long, 0 flat; simple one-position logic)
    """
    df = price_df.copy()

    # Apply indicators
    df = apply_indicators(df, config.get("indicators", []))

    entry_groups = config.get("entry_rules", [])
    exit_groups = config.get("exit_rules", [])

    entry_signal = [0] * len(df)
    exit_signal = [0] * len(df)
    position = [0] * len(df)

    current_pos = 0

    for i in range(len(df)):
        # Check exit first (if in position)
        if current_pos != 0 and exit_groups:
            if any(evaluate_rule_group(df, i, g) for g in exit_groups):
                exit_signal[i] = 1
                current_pos = 0
            else:
                exit_signal[i] = 0

        # If flat, check entries
        if current_pos == 0 and entry_groups:
            if any(evaluate_rule_group(df, i, g) for g in entry_groups):
                entry_signal[i] = 1
                current_pos = 1
            else:
                entry_signal[i] = 0

        position[i] = current_pos

    df["entry_signal"] = entry_signal
    df["exit_signal"] = exit_signal
    df["position"] = position
    return df
