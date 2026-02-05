import yaml
from dataclasses import dataclass
from typing import List, Any


@dataclass
class IndicatorConfig:
    name: str
    type: str
    period: int
    source: str = "close"


@dataclass
class RiskConfig:
    capital: float
    risk_per_trade_pct: float


class StrategyConfig:
    def __init__(
        self,
        name: str,
        market: str,
        timeframe: str,
        indicators: List[IndicatorConfig],
        entry: Any,
        exit: Any,
        risk: RiskConfig,
        raw: dict = None
    ):
        self.name = name
        self.market = market
        self.timeframe = timeframe
        self.indicators = indicators
        self.entry = entry
        self.exit = exit
        self.risk = risk
        self.raw = raw or {}


def parse_strategy_yaml(yaml_text: str) -> StrategyConfig:
    try:
        data = yaml.safe_load(yaml_text)
    except Exception as e:
        raise ValueError(f"Invalid YAML: {str(e)}")

    # Indicators
    indicators = []
    for ind in data.get("indicators", []):
        indicators.append(IndicatorConfig(
            name=ind["name"],
            type=ind["type"],
            period=ind["period"],
            source=ind.get("source", "close")
        ))

    # Risk
    risk_data = data.get("risk", {})
    risk = RiskConfig(
        capital=float(risk_data.get("capital", 10000)),
        risk_per_trade_pct=float(risk_data.get("risk_per_trade_pct", 1.0))
    )

    return StrategyConfig(
        name=data.get("name", "Unnamed Strategy"),
        market=data.get("market", "NAS100"),
        timeframe=data.get("timeframe", "1h"),
        indicators=indicators,
        entry=data.get("entry", {}),
        exit=data.get("exit", {}),
        risk=risk,
        raw=data
    )