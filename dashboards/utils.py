"""Shared helpers for dashboard filters, metrics and placeholder figures."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go

ALL_FILTER_VALUE = "__all__"
DASHBOARD_BACKGROUND = "#1e293b"
DASHBOARD_BORDER = "rgba(148, 163, 184, 0.18)"
ACCENT_COLOR = "#38bdf8"
TEXT_COLOR = "#f8fafc"
MUTED_TEXT_COLOR = "#94a3b8"


def build_dropdown_options(values: Iterable[object], all_label: str) -> list[dict[str, object]]:
    """Build dropdown options with a shared "all" entry.

    Purpose:
        Provide one consistent option-builder for all dashboard filter dropdowns.

    Inputs:
        values: Raw iterable of option values.
        all_label: Label used for the synthetic "all" option.

    Outputs:
        A list of Dash dropdown option dictionaries.
    """

    unique_values: list[object] = []
    for value in values:
        if pd.isna(value):
            continue

        normalized_value = value.item() if hasattr(value, "item") else value
        if isinstance(normalized_value, pd.Timestamp):
            normalized_value = normalized_value.to_pydatetime()
        if normalized_value not in unique_values:
            unique_values.append(normalized_value)

    def sort_key(item: object) -> tuple[int, object]:
        if isinstance(item, datetime):
            return (0, item)
        if isinstance(item, (int, float)):
            return (0, item)
        return (1, str(item).lower())

    sorted_values = sorted(unique_values, key=sort_key)
    options = [{"label": all_label, "value": ALL_FILTER_VALUE}]

    for value in sorted_values:
        if isinstance(value, float) and value.is_integer():
            label = str(int(value))
            option_value = int(value)
        else:
            label = str(value)
            option_value = value
        options.append({"label": label, "value": option_value})

    return options


def filter_dataframe(
    dataframe: pd.DataFrame,
    company_value: object,
    year_value: object,
    company_column: str = "company",
    year_column: str = "year",
) -> pd.DataFrame:
    """Filter a dashboard DataFrame on shared company and year dimensions.

    Purpose:
        Centralize filter application so all dashboards behave consistently.

    Inputs:
        dataframe: DataFrame to filter.
        company_value: Selected company filter value.
        year_value: Selected year filter value.
        company_column: Name of the company column.
        year_column: Name of the year column.

    Outputs:
        The filtered DataFrame.
    """

    filtered = dataframe.copy()

    if company_column in filtered.columns and company_value not in (None, ALL_FILTER_VALUE):
        filtered = filtered[filtered[company_column] == company_value]

    if year_column in filtered.columns and year_value not in (None, ALL_FILTER_VALUE):
        filtered = filtered[filtered[year_column] == year_value]

    return filtered


def format_number(value: float | int | None, suffix: str = "", decimals: int = 0) -> str:
    """Format a numeric KPI value for display.

    Purpose:
        Keep KPI formatting human-readable and visually consistent across pages.

    Inputs:
        value: Numeric value to format.
        suffix: Optional suffix appended to the formatted value.
        decimals: Number of decimal places to display.

    Outputs:
        A formatted string ready for a KPI card.
    """

    if value is None or pd.isna(value):
        return "N/A"

    if abs(float(value)) >= 1_000_000_000:
        scaled_value = float(value) / 1_000_000_000
        return f"{scaled_value:,.{decimals or 1}f}B{suffix}".replace(",", " ")

    if abs(float(value)) >= 1_000_000:
        scaled_value = float(value) / 1_000_000
        return f"{scaled_value:,.{decimals or 1}f}M{suffix}".replace(",", " ")

    return f"{float(value):,.{decimals}f}{suffix}".replace(",", " ")


def create_empty_figure(title: str, message: str) -> go.Figure:
    """Create a styled empty-state figure.

    Purpose:
        Provide a visually consistent placeholder when a dashboard has no data
        for the current selection.

    Inputs:
        title: Figure title.
        message: Empty-state message shown in the plot area.

    Outputs:
        A styled Plotly figure.
    """

    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 16, "color": MUTED_TEXT_COLOR},
    )
    return style_figure(figure, title)


def style_figure(figure: go.Figure, title: str) -> go.Figure:
    """Apply the shared dark dashboard theme to a Plotly figure.

    Purpose:
        Keep visual placeholders and starter charts aligned with the design
        system used by the application shell.

    Inputs:
        figure: Plotly figure to style.
        title: Title displayed above the figure.

    Outputs:
        The styled figure.
    """

    figure.update_layout(
        title={"text": title, "x": 0.02, "font": {"color": TEXT_COLOR, "size": 18}},
        paper_bgcolor=DASHBOARD_BACKGROUND,
        plot_bgcolor=DASHBOARD_BACKGROUND,
        font={"color": TEXT_COLOR},
        margin={"l": 28, "r": 20, "t": 56, "b": 32},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        xaxis={"gridcolor": "rgba(148, 163, 184, 0.12)", "zeroline": False},
        yaxis={"gridcolor": "rgba(148, 163, 184, 0.12)", "zeroline": False},
        hoverlabel={"bgcolor": "#0f172a", "font": {"color": TEXT_COLOR}},
    )
    return figure
