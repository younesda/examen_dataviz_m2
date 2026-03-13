"""Callbacks for the insurance dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State

from dashboards.utils import (
    ACCENT_COLOR,
    ALL_FILTER_VALUE,
    build_dropdown_options,
    create_empty_figure,
    filter_dataframe,
    format_number,
    style_figure,
)


def _build_loss_ratio_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Create a starter loss ratio figure for insurance data.

    Purpose:
        Provide a basic grouped view by company or segment before the advanced
        insurance analytics are introduced in the next phase.

    Inputs:
        dataframe: Filtered insurance DataFrame.

    Outputs:
        A Plotly figure.
    """

    if dataframe.empty or "loss_ratio" not in dataframe.columns:
        return create_empty_figure("Loss Ratio", "No loss ratio data available for this selection.")

    loss_ratio = dataframe.groupby("company", dropna=True)["loss_ratio"].mean().reset_index()
    if loss_ratio.empty:
        return create_empty_figure("Loss Ratio", "No company-level loss ratio data available.")

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=loss_ratio["company"],
            y=loss_ratio["loss_ratio"],
            marker={"color": ACCENT_COLOR},
            name="Loss ratio",
        )
    )
    figure.update_yaxes(tickformat=".0%")
    return style_figure(figure, "Average Loss Ratio")


def _build_profit_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Create a starter profit figure for insurance data.

    Purpose:
        Show a simple annual profitability trend while leaving room for richer
        claim and premium visualizations in phase 3.

    Inputs:
        dataframe: Filtered insurance DataFrame.

    Outputs:
        A Plotly figure.
    """

    if dataframe.empty or "profit" not in dataframe.columns or "year" not in dataframe.columns:
        return create_empty_figure("Profit Trend", "No profit data available for this selection.")

    profit = dataframe.groupby("year", dropna=True)["profit"].sum().reset_index()
    if profit.empty:
        return create_empty_figure("Profit Trend", "No annual profit data available.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=profit["year"],
            y=profit["profit"],
            mode="lines+markers",
            line={"width": 3, "color": ACCENT_COLOR},
            marker={"size": 8},
            name="Profit",
        )
    )
    figure.update_yaxes(tickformat=",.0f")
    return style_figure(figure, "Profit Trend")


def register_insurance_callbacks(app: Dash, dataframe: pd.DataFrame) -> None:
    """Register insurance dashboard callbacks.

    Purpose:
        Wire insurance filters, KPI placeholders and starter figures to the
        shared insurance DataFrame loaded from MongoDB.

    Inputs:
        app: Dash application instance.
        dataframe: Insurance DataFrame used by the insurance page.

    Outputs:
        None. Callbacks are registered on the Dash app.
    """

    @app.callback(
        Output("insurance-year-filter", "options"),
        Output("insurance-year-filter", "value"),
        Input("insurance-company-filter", "value"),
        State("insurance-year-filter", "value"),
    )
    def update_insurance_year_options(
        selected_company: object,
        selected_year: object,
    ) -> tuple[list[dict[str, object]], object]:
        filtered = dataframe
        if selected_company not in (None, ALL_FILTER_VALUE) and "company" in dataframe.columns:
            filtered = dataframe[dataframe["company"] == selected_company]

        options = build_dropdown_options(filtered.get("year", []), "All years")
        valid_values = {option["value"] for option in options}
        next_value = selected_year if selected_year in valid_values else ALL_FILTER_VALUE
        return options, next_value

    @app.callback(
        Output("insurance-kpi-records", "children"),
        Output("insurance-kpi-companies", "children"),
        Output("insurance-kpi-premiums", "children"),
        Output("insurance-kpi-loss-ratio", "children"),
        Output("insurance-claims-graph", "figure"),
        Output("insurance-profit-graph", "figure"),
        Input("insurance-company-filter", "value"),
        Input("insurance-year-filter", "value"),
    )
    def update_insurance_dashboard(
        selected_company: object,
        selected_year: object,
    ) -> tuple[str, str, str, str, go.Figure, go.Figure]:
        filtered = filter_dataframe(dataframe, selected_company, selected_year)

        total_records = format_number(len(filtered))
        total_companies = format_number(filtered["company"].nunique()) if not filtered.empty else "0"
        total_premiums = format_number(filtered["premiums"].sum()) if "premiums" in filtered.columns and not filtered.empty else "N/A"
        average_loss_ratio = (
            f"{filtered['loss_ratio'].mean():.2%}"
            if "loss_ratio" in filtered.columns and not filtered["loss_ratio"].dropna().empty
            else "N/A"
        )

        return (
            total_records,
            total_companies,
            total_premiums,
            average_loss_ratio,
            _build_loss_ratio_figure(filtered),
            _build_profit_figure(filtered),
        )


