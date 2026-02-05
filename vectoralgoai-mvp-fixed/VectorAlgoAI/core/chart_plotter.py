# core/chart_plotter.py
from typing import List

import pandas as pd
import plotly.graph_objects as go


def plot_signals_chart(
    df: pd.DataFrame,
    price_cols=("open", "high", "low", "close"),
    indicator_cols: List[str] = None,
    title: str = "Strategy Signals",
):
    indicator_cols = indicator_cols or []

    fig = go.Figure()

    # Candles
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df[price_cols[0]],
            high=df[price_cols[1]],
            low=df[price_cols[2]],
            close=df[price_cols[3]],
            name="Price",
        )
    )

    # Indicators
    for col in indicator_cols:
        if col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col],
                    mode="lines",
                    name=col,
                )
            )

    # Entry signals
    buys = df[df["entry_signal"] == 1]
    sells = df[df["exit_signal"] == 1]

    fig.add_trace(
        go.Scatter(
            x=buys.index,
            y=buys[price_cols[3]],
            mode="markers",
            marker_symbol="triangle-up",
            marker_size=10,
            name="Buy",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=sells.index,
            y=sells[price_cols[3]],
            mode="markers",
            marker_symbol="triangle-down",
            marker_size=10,
            name="Exit",
        )
    )

    fig.update_layout(title=title, xaxis_rangeslider_visible=False)
    return fig
