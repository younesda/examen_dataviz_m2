"""Solar dashboard layout factory."""

from __future__ import annotations

import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html

from dashboards.utils import ALL_FILTER_VALUE, build_dropdown_options



def _build_kpi_card(card_id: str, label: str) -> dbc.Col:
    """Build one solar KPI card.

    Purpose:
        Reuse a consistent KPI card structure for the solar dashboard.

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


def create_solar_layout(
    dataframe: pd.DataFrame,
    error_message: str | None = None,
) -> html.Div:
    """Create the solar dashboard page layout.

    Purpose:
        Assemble the structural building blocks of the solar dashboard.

    Inputs:
        dataframe: Solar DataFrame used to populate filter options.
        error_message: Optional error message displayed when data loading failed.

    Outputs:
        A Dash ``html.Div`` representing the solar page.
    """

    company_options = build_dropdown_options(dataframe.get("company", []), "All companies")
    year_options = build_dropdown_options(dataframe.get("year", []), "All years")

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Solar Energy Dashboard", className="page-eyebrow"),
                    html.H1("Solar Monitoring Workspace", className="page-title"),
                    html.P(
                        "Structure de base pour les indicateurs de production et d'efficacite.",
                        className="page-subtitle",
                    ),
                    dbc.Alert(
                        error_message or "Solar dataset loaded from MongoDB.",
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
                                    html.Label("Company", className="filter-label"),
                                    dcc.Dropdown(
                                        id="solar-company-filter",
                                        options=company_options,
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
                                        id="solar-year-filter",
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
                    _build_kpi_card("solar-kpi-records", "Records"),
                    _build_kpi_card("solar-kpi-companies", "Companies"),
                    _build_kpi_card("solar-kpi-efficiency", "Avg Efficiency"),
                    _build_kpi_card("solar-kpi-growth", "Avg Annual Growth"),
                ],
                className="g-3 kpi-row",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            dbc.CardBody(
                                dcc.Graph(
                                    id="solar-trend-graph",
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
                                    id="solar-efficiency-graph",
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
