"""Banking dashboard layout factory."""

from __future__ import annotations

import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html

from dashboards.utils import ALL_FILTER_VALUE, build_dropdown_options


def _build_kpi_card(card_id: str, label: str) -> dbc.Col:
    """Build one banking KPI card.

    Purpose:
        Keep the KPI row markup compact and consistent for the banking page.

    Inputs:
        card_id: DOM identifier used by the callback output.
        label: Human-readable KPI label.

    Outputs:
        A ``dbc.Col`` containing the KPI card.
    """

    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Span(label, className="metric-label"),
                    html.H3("--", id=card_id, className="metric-value"),
                ]
            ),
            className="metric-card",
        ),
        xs=12,
        sm=6,
        xl=3,
    )


def create_banking_layout(
    dataframe: pd.DataFrame,
    error_message: str | None = None,
) -> html.Div:
    """Create the banking dashboard page layout.

    Purpose:
        Assemble the structural components of the banking dashboard including
        filters, KPI placeholders and graph containers.

    Inputs:
        dataframe: Banking DataFrame used to populate filter options.
        error_message: Optional error message displayed when data loading failed.

    Outputs:
        A Dash ``html.Div`` representing the banking page.
    """

    bank_options = build_dropdown_options(dataframe.get("company", []), "All banks")
    year_options = build_dropdown_options(dataframe.get("year", []), "All years")

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Banking Dashboard", className="page-eyebrow"),
                    html.H1("Senegal Banking Overview", className="page-title"),
                    html.P(
                        "Base structure prete pour les KPIs, visualisations et analyses avancees.",
                        className="page-subtitle",
                    ),
                    dbc.Alert(
                        error_message or "Banking dataset loaded from MongoDB.",
                        color="warning" if error_message else "info",
                        className="page-alert",
                    ),
                ],
                className="page-header",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Label("Bank", className="filter-label"),
                                    dcc.Dropdown(
                                        id="banking-bank-filter",
                                        options=bank_options,
                                        value=ALL_FILTER_VALUE,
                                        clearable=False,
                                        className="dashboard-dropdown",
                                    ),
                                ]
                            ),
                            className="filter-card",
                        ),
                        md=6,
                        xl=3,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Label("Year", className="filter-label"),
                                    dcc.Dropdown(
                                        id="banking-year-filter",
                                        options=year_options,
                                        value=ALL_FILTER_VALUE,
                                        clearable=False,
                                        className="dashboard-dropdown",
                                    ),
                                ]
                            ),
                            className="filter-card",
                        ),
                        md=6,
                        xl=3,
                    ),
                ],
                className="g-3 filter-row",
            ),
            dbc.Row(
                [
                    _build_kpi_card("banking-kpi-records", "Records"),
                    _build_kpi_card("banking-kpi-banks", "Banks"),
                    _build_kpi_card("banking-kpi-total-bilan", "Total Bilan"),
                    _build_kpi_card("banking-kpi-rentabilite", "Average Rentabilite"),
                ],
                className="g-3 kpi-row",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Graph(
                                    id="banking-overview-graph",
                                    config={"displayModeBar": False},
                                    className="dashboard-graph",
                                )
                            ),
                            className="graph-card",
                        ),
                        xl=7,
                    ),
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Graph(
                                    id="banking-performance-graph",
                                    config={"displayModeBar": False},
                                    className="dashboard-graph",
                                )
                            ),
                            className="graph-card",
                        ),
                        xl=5,
                    ),
                ],
                className="g-3 graph-row",
            ),
        ],
        className="dashboard-page",
    )
