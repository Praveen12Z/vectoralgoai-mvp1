# core/strategy_config.py

import yaml


# --------------------------------------------------------------
# Indicator Config
# --------------------------------------------------------------
class IndicatorConfig:
    def __init__(self, name, type, period, source="close"):
        self.name = name
        self.type = type
        self.period = period
        self.source = source


# --------------------------------------------------------------
# Risk Config
# --------------------------------------------------------------
class RiskConfig:
    def __init__(self, capital, risk_per_trade_pct):
        self.capital = capital
        self.risk_per_trade_pct = risk_per_trade_pct


# --------------------------------------------------------------
# StrategyConfig container
# --------------------------------------------------------------
class StrategyConfig:
    def __init__(
        self,
        name,
        market,
        timeframe,
        indicators,
        entry,
        exit,
        risk,
        raw=None,
    ):
        """
        raw = original parsed YAML dict (needed by backtester_adapter / PRO engine)
        """
        self.name = name
        self.market = market
        self.timeframe = timeframe
        self.indicators = indicators
        self.entry = entry
        self.exit = exit
        self.risk = risk
        self.raw = raw or {}   # ✅ this fixes AttributeError: cfg.raw


# --------------------------------------------------------------
# Rule Parsing
# --------------------------------------------------------------
def parse_comparison_rules(rule_list):
    """
    Converts comparison rules (left/op/right) into PRO-engine format:

    [
        {
          "all": [
             {"left": "...", "op": "...", "right": "..."},
             ...
          ]
        }
    ]
    """
    conditions = []

    for r in rule_list:
        # Skip non-comparison rules (e.g. ATR SL/TP blocks)
        if "type" in r:
            continue

        if "left" not in r or "op" not in r or "right" not in r:
            raise ValueError("Each comparison rule must contain left, op, right.")

        conditions.append(
            {
                "left": r["left"],
                "op": r["op"],
                "right": r["right"],
            }
        )

    if len(conditions) == 0:
        return []  # no comparison rules

    # Single AND-group – all conditions must be true
    return [{"all": conditions}]


def parse_atr_rules(rule_list):
    """
    Extract ATR SL/TP rules unchanged, for use by the PRO engine:

    [
        {"type": "atr_sl", "atr_col": "...", "multiple": ...},
        {"type": "atr_tp", "atr_col": "...", "multiple": ...},
        ...
    ]
    """
    atr_rules = []

    for r in rule_list:
        if "type" in r and r["type"] in ["atr_sl", "atr_tp"]:
            atr_rules.append(r)

    return atr_rules


# --------------------------------------------------------------
# YAML PARSER
# --------------------------------------------------------------
def parse_strategy_yaml(text: str) -> StrategyConfig:
    """
    Parse YAML -> StrategyConfig for the PRO backtester.
    Keeps original YAML dict in cfg.raw for advanced features.
    """
    data = yaml.safe_load(text)

    # ---------------------------------------------
    # INDICATORS
    # ---------------------------------------------
    indicators = [
        IndicatorConfig(
            ind["name"],
            ind["type"],
            ind["period"],
            ind.get("source", "close"),
        )
        for ind in data.get("indicators", [])
    ]

    # ---------------------------------------------
    # ENTRY RULES (comparison only – no ATR here)
    # ---------------------------------------------
    entry_long_cmp = parse_comparison_rules(data["entry"]["long"])
    entry_short_cmp = parse_comparison_rules(data["entry"]["short"])

    entry = type(
        "EntryRules",
        (),
        {
            "long": entry_long_cmp,
            "short": entry_short_cmp,
        },
    )

    # ---------------------------------------------
    # EXIT RULES (ATR preferred, fallback to comparisons)
    # ---------------------------------------------
    exit_long_cmp = parse_comparison_rules(data["exit"]["long"])
    exit_short_cmp = parse_comparison_rules(data["exit"]["short"])

    exit_long_atr = parse_atr_rules(data["exit"]["long"])
    exit_short_atr = parse_atr_rules(data["exit"]["short"])

    # If ATR rules exist, we use those as primary exit spec.
    # PRO engine reads these directly; rule_engine handles only comparison groups.
    exit = type(
        "ExitRules",
        (),
        {
            "long": exit_long_atr if len(exit_long_atr) > 0 else exit_long_cmp,
            "short": exit_short_atr if len(exit_short_atr) > 0 else exit_short_cmp,
        },
    )

    # ---------------------------------------------
    # RISK
    # ---------------------------------------------
    risk = RiskConfig(
        data["risk"]["capital"],
        data["risk"]["risk_per_trade_pct"],
    )

    # ---------------------------------------------
    # FINAL StrategyConfig RETURN
    # ---------------------------------------------
    return StrategyConfig(
        name=data["name"],
        market=data["market"],
        timeframe=data["timeframe"],
        indicators=indicators,
        entry=entry,
        exit=exit,
        risk=risk,
        raw=data,  # ✅ keep full original YAML for adapter / advanced features
    )
