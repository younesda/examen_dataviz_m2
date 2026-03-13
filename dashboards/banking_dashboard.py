"""Callbacks for the banking dashboard."""

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


def _build_bilan_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Create a starter overview figure for banking data.

    Purpose:
        Show a lightweight first visual structure based on annual balance-sheet
        totals while the advanced charts are reserved for phase 3.

    Inputs:
        dataframe: Filtered banking DataFrame.

    Outputs:
        A Plotly figure.
    """

    if dataframe.empty or "bilan" not in dataframe.columns:
        return create_empty_figure("Banking Overview", "No banking data available for this selection.")

    overview = dataframe.groupby("year", dropna=True)["bilan"].sum().reset_index()
    if overview.empty:
        return create_empty_figure("Banking Overview", "No annual balance data available.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=overview["year"],
            y=overview["bilan"],
            mode="lines+markers",
            line={"width": 3, "color": ACCENT_COLOR},
            marker={"size": 8},
            name="Bilan",
        )
    )
    figure.update_yaxes(tickformat=",.0f")
    return style_figure(figure, "Banking Overview")


def _build_resultat_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Create a starter profitability figure for banking data.

    Purpose:
        Provide a basic result distribution by bank while keeping the page ready
        for richer visuals in the next project phase.

    Inputs:
        dataframe: Filtered banking DataFrame.

    Outputs:
        A Plotly figure.
    """

    if dataframe.empty or "resultat_net" not in dataframe.columns:
        return create_empty_figure("Net Result", "No profitability data available for this selection.")

    profitability = dataframe.groupby("company", dropna=True)["resultat_net"].sum().reset_index()
    if profitability.empty:
        return create_empty_figure("Net Result", "No bank-level profitability data available.")

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=profitability["company"],
            y=profitability["resultat_net"],
            marker={"color": ACCENT_COLOR},
            name="Net result",
        )
    )
    figure.update_yaxes(tickformat=",.0f")
    return style_figure(figure, "Net Result by Bank")


def register_banking_callbacks(app: Dash, dataframe: pd.DataFrame) -> None:
    """Register banking dashboard callbacks.

    Purpose:
        Wire banking filters, KPI placeholders and starter figures to the shared
        banking DataFrame loaded from MongoDB.

    Inputs:
        app: Dash application instance.
        dataframe: Banking DataFrame used by the banking page.

    Outputs:
        None. Callbacks are registered on the Dash app.
    """

    @app.callback(
        Output("banking-year-filter", "options"),
        Output("banking-year-filter", "value"),
        Input("banking-bank-filter", "value"),
        State("banking-year-filter", "value"),
    )
    def update_banking_year_options(
        selected_bank: object,
        selected_year: object,
    ) -> tuple[list[dict[str, object]], object]:
        filtered = dataframe
        if selected_bank not in (None, ALL_FILTER_VALUE) and "company" in dataframe.columns:
            filtered = dataframe[dataframe["company"] == selected_bank]

        options = build_dropdown_options(filtered.get("year", []), "All years")
        valid_values = {option["value"] for option in options}
        next_value = selected_year if selected_year in valid_values else ALL_FILTER_VALUE
        return options, next_value

    @app.callback(
        Output("banking-kpi-records", "children"),
        Output("banking-kpi-banks", "children"),
        Output("banking-kpi-total-bilan", "children"),
        Output("banking-kpi-rentabilite", "children"),
        Output("banking-overview-graph", "figure"),
        Output("banking-performance-graph", "figure"),
        Input("banking-bank-filter", "value"),
        Input("banking-year-filter", "value"),
    )
    def update_banking_dashboard(
        selected_bank: object,
        selected_year: object,
    ) -> tuple[str, str, str, str, go.Figure, go.Figure]:
        filtered = filter_dataframe(dataframe, selected_bank, selected_year)

        total_records = format_number(len(filtered))
        total_banks = format_number(filtered["company"].nunique()) if not filtered.empty else "0"
        total_bilan = format_number(filtered["bilan"].sum(), suffix=" FCFA") if "bilan" in filtered.columns and not filtered.empty else "N/A"
        average_rentabilite = (
            f"{filtered['rentabilite'].mean():.2%}"
            if "rentabilite" in filtered.columns and not filtered["rentabilite"].dropna().empty
            else "N/A"
        )

        return (
            total_records,
            total_banks,
            total_bilan,
            average_rentabilite,
            _build_bilan_figure(filtered),
            _build_resultat_figure(filtered),
        )


