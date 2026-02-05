# core/rule_engine.py

import operator
import pandas as pd

# -----------------------------------------------------------
# Operator registry
# -----------------------------------------------------------
OP_MAP = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

# -----------------------------------------------------------
# Helper: get value
# -----------------------------------------------------------
def _get_value(row, key):
    if isinstance(key, (int, float)):
        return float(key)
    return row[key]

# -----------------------------------------------------------
# Basic condition evaluation
# -----------------------------------------------------------
def eval_condition(df: pd.DataFrame, idx: int, cond: dict) -> bool:
    op = cond["op"]
    left = cond["left"]
    right = cond["right"]

    cur = df.iloc[idx]
    prev = df.iloc[idx - 1] if idx > 0 else cur

    # CROSSOVER
    if op == "crosses_above":
        return (
            _get_value(prev, left) <= _get_value(prev, right)
            and _get_value(cur, left) > _get_value(cur, right)
        )

    if op == "crosses_below":
        return (
            _get_value(prev, left) >= _get_value(prev, right)
            and _get_value(cur, left) < _get_value(cur, right)
        )

    # NORMAL comparisons
    if op not in OP_MAP:
        raise ValueError(f"Unknown operator: {op}")

    return OP_MAP[op](_get_value(cur, left), _get_value(cur, right))

# -----------------------------------------------------------
# Group evaluator (ALL / ANY)
# -----------------------------------------------------------
def eval_rule_group(df: pd.DataFrame, idx: int, group: dict) -> bool:

    # 🚨 SKIP ATR RULES — they have no ALL/ANY, handled in engine
    if "type" in group:
        return False

    if "all" in group:
        return all(eval_condition(df, idx, c) for c in group["all"])

    if "any" in group:
        return any(eval_condition(df, idx, c) for c in group["any"])

    raise ValueError("Rule group must contain 'all' or 'any'.")

# -----------------------------------------------------------
# Entry / Exit wrappers
# -----------------------------------------------------------
def check_entry_long(df, idx, entry_cfg):
    return any(
        eval_rule_group(df, idx, g)
        for g in entry_cfg.long
        if "type" not in g     # skip ATR rules
    )

def check_entry_short(df, idx, entry_cfg):
    return any(
        eval_rule_group(df, idx, g)
        for g in entry_cfg.short
        if "type" not in g
    )

def check_exit_long(df, idx, exit_cfg):
    return any(
        eval_rule_group(df, idx, g)
        for g in exit_cfg.long
        if "type" not in g    # skip ATR rules
    )

def check_exit_short(df, idx, exit_cfg):
    return any(
        eval_rule_group(df, idx, g)
        for g in exit_cfg.short
        if "type" not in g
    )
