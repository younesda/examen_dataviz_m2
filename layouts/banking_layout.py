"""Banking dashboard layout factory."""

from __future__ import annotations

import pandas as pd
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table
from dash.dash_table.Format import Format, Group, Scheme

from dashboards.utils import ALL_FILTER_VALUE, build_dropdown_options


def _build_kpi_card(card_id: str, label: str, helper_text: str) -> dbc.Col:
    """Build one KPI card for the banking dashboard.

    Purpose:
        Keep the KPI section visually consistent while exposing clear business
        metrics for the banking dashboard.

    Inputs:
        card_id: DOM identifier used by Dash callbacks.
        label: Human-readable KPI title.
        helper_text: Short supporting text displayed under the title.

    Outputs:
        A Bootstrap column containing a styled KPI card.
    """

    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Span(label, className="metric-label"),
                    html.H3("--", id=card_id, className="metric-value"),
                    html.P(helper_text, className="metric-helper"),
                ]
            ),
            className="metric-card h-100",
        ),
        xs=12,
        sm=6,
        xl=3,
    )



def _build_graph_card(graph_id: str, title: str) -> dbc.Card:
    """Create a reusable graph card container.

    Purpose:
        Reduce repeated layout markup for Plotly graph sections and keep all
        chart containers aligned with the design system.

    Inputs:
        graph_id: Graph component identifier.
        title: Card title shown above the graph.

    Outputs:
        A styled ``dbc.Card`` containing a ``dcc.Graph`` placeholder.
    """

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(title, className="graph-card-title"),
                dcc.Graph(
                    id=graph_id,
                    config={"displayModeBar": False},
                    className="dashboard-graph",
                ),
            ]
        ),
        className="graph-card h-100",
    )



def _build_ranking_table() -> dash_table.DataTable:
    """Create the interactive banking ranking table.

    Purpose:
        Provide a sortable, filterable bank ranking section that complements
        the graphical analysis with precise numeric values.

    Inputs:
        None.

    Outputs:
        A configured Dash DataTable instance.
    """

    number_format = Format(group=Group.yes, precision=0, scheme=Scheme.fixed)

    return dash_table.DataTable(
        id="banking-ranking-table",
        columns=[
            {"name": "Bank", "id": "company", "type": "text"},
            {"name": "Bilan (FCFA)", "id": "bilan", "type": "numeric", "format": number_format},
            {
                "name": "Fonds Propres (FCFA)",
                "id": "fonds_propres",
                "type": "numeric",
                "format": number_format,
            },
            {
                "name": "Resultat Net (FCFA)",
                "id": "resultat_net",
                "type": "numeric",
                "format": number_format,
            },
            {
                "name": "Produit Net Bancaire (FCFA)",
                "id": "produit_net_bancaire",
                "type": "numeric",
                "format": number_format,
            },
        ],
        data=[],
        sort_action="native",
        filter_action="native",
        page_action="native",
        page_size=10,
        style_table={"overflowX": "auto"},
        style_as_list_view=True,
        style_header={
            "backgroundColor": "#0f172a",
            "color": "#f8fafc",
            "fontWeight": "700",
            "border": "1px solid rgba(148, 163, 184, 0.18)",
            "padding": "0.85rem 0.75rem",
        },
        style_cell={
            "backgroundColor": "#1e293b",
            "color": "#f8fafc",
            "border": "1px solid rgba(148, 163, 184, 0.10)",
            "padding": "0.75rem",
            "fontFamily": "Bahnschrift, Trebuchet MS, sans-serif",
            "textAlign": "left",
            "minWidth": "130px",
            "width": "130px",
            "maxWidth": "240px",
        },
        style_data_conditional=[
            {
                "if": {"row_index": "odd"},
                "backgroundColor": "rgba(36, 52, 73, 0.7)",
            }
        ],
    )



def create_banking_layout(
    dataframe: pd.DataFrame,
    error_message: str | None = None,
) -> html.Div:
    """Create the advanced banking dashboard page layout.

    Purpose:
        Assemble filters, KPI cards, multi-tab analytics and the ranking table
        used by the Senegal banking dashboard.

    Inputs:
        dataframe: Banking DataFrame used to populate filter dropdowns.
        error_message: Optional loading issue displayed in the page header.

    Outputs:
        A Dash ``html.Div`` representing the full banking page.
    """

    bank_options = build_dropdown_options(dataframe.get("company", []), "All banks")
    year_options = build_dropdown_options(dataframe.get("year", []), "All years")

    return html.Div(
        [
            html.Div(
                [
                    html.Span("Banking Dashboard", className="page-eyebrow"),
                    html.H1("Senegal Banking Intelligence Hub", className="page-title"),
                    html.P(
                        "KPIs, peer comparison, market structure and operational analytics for Senegalese banks.",
                        className="page-subtitle",
                    ),
                    dbc.Alert(
                        error_message or "Banking dataset loaded from MongoDB and ready for interactive analysis.",
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
                                        id="banking-bank-filter",
                                        options=bank_options,
                                        value=ALL_FILTER_VALUE,
                                        clearable=False,
                                        className="dashboard-dropdown",
                                    ),
                                ]
                            ),
                            className="filter-card h-100",
                        ),
                        xs=12,
                        lg=6,
                        xl=4,
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
                            className="filter-card h-100",
                        ),
                        xs=12,
                        lg=6,
                        xl=4,
                    ),
                ],
                className="g-3 filter-row",
            ),
            dbc.Row(
                [
                    _build_kpi_card("banking-kpi-total-assets", "Total Assets", "Aggregate bilan across the current selection."),
                    _build_kpi_card("banking-kpi-total-funds", "Total Fonds Propres", "Capital base supporting the selected perimeter."),
                    _build_kpi_card("banking-kpi-pnb", "Produit Net Bancaire", "Commercial banking revenue generated in scope."),
                    _build_kpi_card("banking-kpi-net-result", "Resultat Net", "Bottom-line performance for the filtered banks."),
                ],
                className="g-3 kpi-row",
            ),
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div("Multi-Tab Analytics", className="section-title"),
                        dbc.Tabs(
                            [
                                dbc.Tab(
                                    label="Market Overview",
                                    tab_id="banking-market-overview",
                                    children=[
                                        dbc.Row(
                                            [
                                                dbc.Col(_build_graph_card("banking-market-share-graph", "Market Share by Total Assets"), xl=5),
                                                dbc.Col(_build_graph_card("banking-sector-evolution-graph", "Sector Evolution Over Time"), xl=7),
                                            ],
                                            className="g-3 tab-row",
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(_build_graph_card("banking-top-banks-graph", "Top Banks by Total Assets"), xs=12),
                                            ],
                                            className="g-3 tab-row",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Bank Comparison",
                                    tab_id="banking-bank-comparison",
                                    children=[
                                        dbc.Row(
                                            [
                                                dbc.Col(_build_graph_card("banking-comparison-profit-graph", "Net Profit Comparison"), xl=4),
                                                dbc.Col(_build_graph_card("banking-comparison-funds-graph", "Equity Comparison"), xl=4),
                                                dbc.Col(_build_graph_card("banking-comparison-pnb-graph", "PNB Comparison"), xl=4),
                                            ],
                                            className="g-3 tab-row",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Financial Performance",
                                    tab_id="banking-financial-performance",
                                    children=[
                                        dbc.Row(
                                            [
                                                dbc.Col(_build_graph_card("banking-profit-vs-assets-graph", "Profit vs Assets"), xl=6),
                                                dbc.Col(_build_graph_card("banking-profit-growth-graph", "Profit Growth by Bank"), xl=6),
                                            ],
                                            className="g-3 tab-row",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Operational Analysis",
                                    tab_id="banking-operational-analysis",
                                    children=[
                                        dbc.Row(
                                            [
                                                dbc.Col(_build_graph_card("banking-agency-vs-assets-graph", "Agencies vs Assets"), xl=6),
                                                dbc.Col(_build_graph_card("banking-workforce-vs-performance-graph", "Workforce vs Performance"), xl=6),
                                            ],
                                            className="g-3 tab-row",
                                        ),
                                    ],
                                ),
                            ],
                            class_name="analytics-tabs",
                            active_tab="banking-market-overview",
                        ),
                    ]
                ),
                className="graph-card analytics-shell",
            ),
            dbc.Card(
                dbc.CardBody(
                    [
                        html.Div("Bank Ranking", className="section-title"),
                        html.P(
                            "Interactive ranking of banks by net result within the selected perimeter.",
                            className="section-subtitle",
                        ),
                        _build_ranking_table(),
                    ]
                ),
                className="graph-card ranking-card",
            ),
        ],
        className="dashboard-page",
    )
