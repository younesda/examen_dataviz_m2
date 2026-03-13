"""Callbacks for the solar dashboard."""

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


def _build_efficiency_trend_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Create a starter trend figure for solar efficiency.

    Purpose:
        Expose a simple time-series placeholder to validate the data pipeline and
        callback structure before advanced visual analytics are implemented.

    Inputs:
        dataframe: Filtered solar DataFrame.

    Outputs:
        A Plotly figure.
    """

    if dataframe.empty or "date" not in dataframe.columns or "production_efficiency" not in dataframe.columns:
        return create_empty_figure("Solar Trend", "No solar efficiency data available for this selection.")

    trend = dataframe.sort_values("date")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=trend["date"],
            y=trend["production_efficiency"],
            mode="lines",
            line={"width": 3, "color": ACCENT_COLOR},
            name="Efficiency",
        )
    )
    return style_figure(figure, "Production Efficiency Trend")


def _build_annual_growth_figure(dataframe: pd.DataFrame) -> go.Figure:
    """Create a starter annual growth figure for solar data.

    Purpose:
        Provide a lightweight annual view that will later be replaced by richer
        energy production visualizations.

    Inputs:
        dataframe: Filtered solar DataFrame.

    Outputs:
        A Plotly figure.
    """

    if dataframe.empty or "year" not in dataframe.columns or "annual_growth" not in dataframe.columns:
        return create_empty_figure("Annual Growth", "No annual growth data available for this selection.")

    growth = dataframe.groupby("year", dropna=True)["annual_growth"].mean().reset_index()
    if growth.empty:
        return create_empty_figure("Annual Growth", "No annual growth data available.")

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=growth["year"],
            y=growth["annual_growth"],
            marker={"color": ACCENT_COLOR},
            name="Annual growth",
        )
    )
    figure.update_yaxes(tickformat=".0%")
    return style_figure(figure, "Average Annual Growth")


def register_solar_callbacks(app: Dash, dataframe: pd.DataFrame) -> None:
    """Register solar dashboard callbacks.

    Purpose:
        Wire solar filters, KPI placeholders and starter figures to the shared
        solar DataFrame loaded from MongoDB.

    Inputs:
        app: Dash application instance.
        dataframe: Solar DataFrame used by the solar page.

    Outputs:
        None. Callbacks are registered on the Dash app.
    """

    @app.callback(
        Output("solar-year-filter", "options"),
        Output("solar-year-filter", "value"),
        Input("solar-company-filter", "value"),
        State("solar-year-filter", "value"),
    )
    def update_solar_year_options(
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
        Output("solar-kpi-records", "children"),
        Output("solar-kpi-companies", "children"),
        Output("solar-kpi-efficiency", "children"),
        Output("solar-kpi-growth", "children"),
        Output("solar-trend-graph", "figure"),
        Output("solar-efficiency-graph", "figure"),
        Input("solar-company-filter", "value"),
        Input("solar-year-filter", "value"),
    )
    def update_solar_dashboard(
        selected_company: object,
        selected_year: object,
    ) -> tuple[str, str, str, str, go.Figure, go.Figure]:
        filtered = filter_dataframe(dataframe, selected_company, selected_year)

        total_records = format_number(len(filtered))
        total_companies = format_number(filtered["company"].nunique()) if not filtered.empty else "0"
        average_efficiency = (
            f"{filtered['production_efficiency'].mean():.2f}"
            if "production_efficiency" in filtered.columns and not filtered["production_efficiency"].dropna().empty
            else "N/A"
        )
        average_growth = (
            f"{filtered['annual_growth'].mean():.2%}"
            if "annual_growth" in filtered.columns and not filtered["annual_growth"].dropna().empty
            else "N/A"
        )

        return (
            total_records,
            total_companies,
            average_efficiency,
            average_growth,
            _build_efficiency_trend_figure(filtered),
            _build_annual_growth_figure(filtered),
        )


