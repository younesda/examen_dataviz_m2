"""Callbacks and analytics for the premium Senegal banking dashboard."""

from __future__ import annotations

import base64
import re
import unicodedata
from io import BytesIO
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dash_table, dcc, html
from dash.exceptions import PreventUpdate
from flask import Flask
from dash.dash_table.Format import Format, Group, Scheme
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from dashboards.utils import ALL_FILTER_VALUE, build_dropdown_options, format_number


PREMIUM_NUMBER_FORMAT = Format(group=Group.yes, precision=0, scheme=Scheme.fixed)
PREMIUM_PERCENT_FORMAT = Format(precision=2, scheme=Scheme.percentage)
GRAPH_HEIGHT = 320
GRAPH_HEIGHT_TALL = 420


def _build_filter_group(label: str, component: dcc.Dropdown) -> html.Div:
    return html.Div(
        [
            html.Label(label),
            component,
        ],
        className="filter-group",
    )



def _build_kpi_card(
    card_id: str,
    label: str,
    code: str,
    subtitle: str,
    meta_label: str,
    context_label: str,
    card_class: str = "",
) -> html.Div:
    class_names = "kpi-card"
    if card_class:
        class_names = f"{class_names} {card_class}"

    return html.Div(
        [
            html.Div(
                [
                    html.Div(label, className="kpi-label"),
                    html.Div(code, className="kpi-chip"),
                ],
                className="kpi-head",
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("--", id=card_id, className="kpi-value"),
                            html.Div(subtitle, className="kpi-sub"),
                        ]
                    ),
                    html.Span(
                        [html.Strong("—"), html.Small("vs N-1")],
                        className="kpi-trend neutral",
                        id=f"{card_id}-trend",
                    ),
                ],
                className="kpi-value-row",
            ),
            html.Div(
                [
                    html.Span(meta_label, className="kpi-context"),
                    html.Span(context_label, className="kpi-context"),
                ],
                className="kpi-meta",
            ),
        ],
        className=class_names,
    )



def _build_bank_focus_kpi(card_id: str, label: str) -> html.Div:
    return html.Div(
        [
            html.Div(label, className="bkpi-l"),
            html.Div("--", id=card_id, className="bkpi-v"),
        ],
        className="bkpi",
    )



def _build_ratio_card(card_id: str, label: str, description: str) -> html.Div:
    return html.Div(
        [
            html.Div(label, className="ratio-name"),
            html.Div("--", id=card_id, className="ratio-value"),
            html.Div(
                html.Div(
                    style={"width": "0%"},
                    className="ratio-bar-fill",
                    id=f"{card_id}-bar",
                ),
                className="ratio-bar-bg",
            ),
            html.Div(description, className="ratio-desc"),
        ],
        className="ratio-card",
    )



def _build_graph_panel(
    graph_id: str,
    title: str,
    dot_class: str = "",
    graph_container_class: str = "chart-wrap graph-container",
    height: int | None = None,
) -> dbc.Card:
    dot_classes = "dot"
    if dot_class:
        dot_classes = f"{dot_classes} {dot_class}"

    return dbc.Card(
        [
            html.Div(
                [
                    html.Span(className=dot_classes),
                    title,
                ],
                className="card-title",
            ),
            html.Div(
                dcc.Graph(
                    id=graph_id,
                    figure=go.Figure(),
                    config={"displayModeBar": False},
                    className="dash-graph banking-plot",
                    style={"height": f"{height or GRAPH_HEIGHT}px", "width": "100%"},
                ),
                className=graph_container_class,
            ),
        ],
        class_name="card card-graph h-100",
    )



def _build_table(table_id: str, columns: list[dict[str, object]], page_size: int) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=[],
        page_action="native",
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_as_list_view=True,
        style_header={
            "backgroundColor": "#f0f4f8",
            "color": "#7f8c8d",
            "fontWeight": "700",
            "fontSize": "10px",
            "textTransform": "uppercase",
            "letterSpacing": "0.5px",
            "border": "none",
            "borderBottom": "2px solid #dce3ec",
            "padding": "9px 12px",
        },
        style_cell={
            "backgroundColor": "#ffffff",
            "color": "#1c2833",
            "border": "none",
            "borderBottom": "1px solid #eef1f5",
            "padding": "9px 12px",
            "fontFamily": "Segoe UI, system-ui, sans-serif",
            "fontSize": "13px",
            "textAlign": "left",
            "minWidth": "120px",
            "width": "120px",
            "maxWidth": "240px",
            "whiteSpace": "normal",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#ffffff"},
        ],
    )



def _build_ranking_table() -> dash_table.DataTable:
    return _build_table(
        "banking-ranking-table",
        [
            {"name": "Banque", "id": "company", "type": "text"},
            {"name": "Groupe", "id": "groupe_bancaire", "type": "text"},
            {"name": "Total actif", "id": "bilan", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "PNB", "id": "produit_net_bancaire", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "Resultat net", "id": "resultat_net", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "Capitaux propres", "id": "fonds_propres", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "ROA", "id": "roa", "type": "numeric", "format": PREMIUM_PERCENT_FORMAT},
            {"name": "ROE", "id": "roe", "type": "numeric", "format": PREMIUM_PERCENT_FORMAT},
        ],
        page_size=10,
    )



def _build_raw_data_table() -> dash_table.DataTable:
    return _build_table(
        "banking-raw-data-table",
        [
            {"name": "Annee", "id": "year", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "Banque", "id": "company", "type": "text"},
            {"name": "Groupe", "id": "groupe_bancaire", "type": "text"},
            {"name": "Actif", "id": "bilan", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "PNB", "id": "produit_net_bancaire", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "Resultat", "id": "resultat_net", "type": "numeric", "format": PREMIUM_NUMBER_FORMAT},
            {"name": "ROA", "id": "roa", "type": "numeric", "format": PREMIUM_PERCENT_FORMAT},
            {"name": "ROE", "id": "roe", "type": "numeric", "format": PREMIUM_PERCENT_FORMAT},
        ],
        page_size=14,
    )


# --- Main layout ------------------------------------------------------------


def create_banking_layout(dataframe: pd.DataFrame, error_message: str | None = None) -> html.Div:
    """Create the banking dashboard layout aligned with the reference HTML."""

    prepared_dataframe = _prepare_banking_dataframe(dataframe)
    bank_values = prepared_dataframe.get("company", prepared_dataframe.get("bank_name", []))
    group_values = prepared_dataframe.get("groupe_bancaire", [])
    year_values = prepared_dataframe.get("year", prepared_dataframe.get("annee", []))

    sorted_bank_values = sorted(pd.Series(bank_values).dropna().unique())
    bank_options = [{"label": "Toutes", "value": ALL_FILTER_VALUE}]
    bank_options.extend({"label": str(bank_name), "value": bank_name} for bank_name in sorted_bank_values)
    group_options = build_dropdown_options(group_values, "Tous")
    year_options = build_dropdown_options(year_values, "Toutes")
    total_banks = int(prepared_dataframe["company"].nunique()) if "company" in prepared_dataframe.columns else 0

    return html.Div(
        [
            dcc.Download(id="banking-export-download"),
            html.Header(
                [
                    html.Div(
                        [
                            html.Div("ISM", className="header-logo"),
                            html.Div(
                                [
                                    html.Div("Secteur Bancaire Sénégalais", className="header-title"),
                                    html.Div("Tableau de Bord Analytique · 2015–2022 · M2 Big Data", className="header-sub"),
                                ]
                            ),
                        ],
                        className="header-left",
                    ),
                    html.Div(
                        [
                            html.Div(f"{total_banks} banques · 2015–2022", className="header-badge"),
                            dbc.Button(
                                "Retour accueil",
                                href="/",
                                class_name="btn-pdf no-print",
                                color="link",
                            ),
                            dbc.Button(
                                "Exporter PDF",
                                id="banking-export-pdf-button",
                                class_name="btn-pdf no-print",
                                color="link",
                            ),
                        ],
                        className="header-actions",
                    ),
                ]
            ),
            html.Div(
                [
                    _build_filter_group(
                        "Année",
                        dcc.Dropdown(
                            id="banking-year-filter",
                            options=year_options,
                            value=ALL_FILTER_VALUE,
                            clearable=False,
                            className="banking-select",
                        ),
                    ),
                    html.Div(className="filter-divider"),
                    _build_filter_group(
                        "Groupe",
                        dcc.Dropdown(
                            id="banking-group-filter",
                            options=group_options,
                            value=ALL_FILTER_VALUE,
                            clearable=False,
                            className="banking-select",
                        ),
                    ),
                    html.Div(className="filter-divider"),
                    _build_filter_group(
                        "Banque",
                        dcc.Dropdown(
                            id="banking-bank-filter",
                            options=bank_options,
                            value=ALL_FILTER_VALUE,
                            clearable=False,
                            className="banking-select",
                        ),
                    ),
                    html.Button(
                        "↺ Réinitialiser",
                        id="banking-reset-btn",
                        className="btn-reset no-print",
                        n_clicks=0,
                    ),
                ],
                className="filters-bar no-print",
            ),
            html.Div(
                [
                    html.Div(error_message, className="card mb") if error_message else None,
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                label="📊 Vue Sectorielle",
                                tab_id="banking-tab-sector-view",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    html.Div(
                                        [
                                            _build_kpi_card("banking-kpi-sector-assets", "Total Actif", "ACTIF", "Volume consolide du secteur bancaire", "Base FCFA", "2015-2022", "featured navy"),
                                            _build_kpi_card("banking-kpi-sector-pnb", "Produit Net Bancaire", "PNB", "Produit net bancaire consolide", "Performance", "Scope courant", "gold"),
                                            _build_kpi_card("banking-kpi-sector-net-result", "Resultat Net", "RN", "Profitabilite nette du secteur", "Rentabilite", "Scope courant", "green"),
                                            _build_kpi_card("banking-kpi-sector-equity", "Capitaux Propres", "CP", "Fonds propres consolides", "Solidite", "Snapshot", "navy"),
                                            _build_kpi_card("banking-kpi-sector-bank-count", "Banques actives", "BANKS", "Institutions visibles dans le perimetre", "Couverture", "Perimetre", ""),
                                            _build_kpi_card("banking-kpi-sector-roa", "ROA moyen", "ROA", "Rentabilite de l actif moyen", "Rendement", "Secteur", "purple"),
                                            _build_kpi_card("banking-kpi-sector-roe", "ROE moyen", "ROE", "Rentabilite des fonds propres", "Rendement", "Secteur", "gold"),
                                        ],
                                        className="kpi-grid",
                                        id="kpi-grid",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-sector-assets-graph", "Évolution du Total Actif Sectoriel (Mds FCFA)", ""), xl=8),
                                            dbc.Col(_build_graph_panel("banking-sector-group-share-graph", "Répartition par Groupe (Total Actif)", "gold"), xl=4),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-sector-pnb-graph", "Évolution PNB Sectoriel (Mds FCFA)", "green"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-sector-result-graph", "Évolution Résultat Net (Mds FCFA)", "red"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-sector-ressources-emplois-graph", "Ressources & Emplois (Mds FCFA)", "navy"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-sector-funds-graph", "Capitaux Propres du Secteur (Mds FCFA)", "purple"), xl=6),
                                        ],
                                        class_name="g-4",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="🏦 Bilan & Structure",
                                tab_id="banking-tab-balance-structure",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    html.Div(
                                        [
                                            _build_bank_focus_kpi("banking-bilan-kpi-assets", "Total Actif"),
                                            _build_bank_focus_kpi("banking-bilan-kpi-emplois", "Emplois"),
                                            _build_bank_focus_kpi("banking-bilan-kpi-ressources", "Ressources"),
                                            _build_bank_focus_kpi("banking-bilan-kpi-equity", "Capitaux Propres"),
                                            _build_bank_focus_kpi("banking-bilan-kpi-nim", "NIM"),
                                            _build_bank_focus_kpi("banking-bilan-kpi-cir", "CIR"),
                                        ],
                                        className="bank-kpis",
                                        style={"marginBottom": "20px"},
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-structure-assets-graph", "Structure du Bilan — Actif (année sélectionnée)", ""), xl=6),
                                            dbc.Col(_build_graph_panel("banking-structure-liabilities-graph", "Structure du Bilan — Passif & Capitaux", "gold"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-structure-client-graph", "Évolution Créances Clientèle vs Dettes Clientèle", "green", "chart-wrap tall graph-container"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-structure-ratio-graph", "Top Banques — Ratio Emplois/Ressources", "red", "chart-wrap tall graph-container"), xl=6),
                                        ],
                                        class_name="g-4",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="📐 Ratios Financiers",
                                tab_id="banking-tab-ratios",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    html.Div(
                                        [
                                            _build_ratio_card("banking-ratio-roa", "ROA", "Rentabilite moyenne des actifs."),
                                            _build_ratio_card("banking-ratio-roe", "ROE", "Rentabilite moyenne des fonds propres."),
                                            _build_ratio_card("banking-ratio-nim", "NIM", "Marge nette d'intermediation."),
                                            _build_ratio_card("banking-ratio-cir", "Coefficient exploitation", "Efficacite d'exploitation du secteur."),
                                            _build_ratio_card("banking-ratio-er", "Emplois / Ressources", "Ratio emplois sur ressources."),
                                        ],
                                        className="ratio-grid",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-ratios-roa-roe-graph", "Évolution ROA & ROE du Secteur (%)", ""), xl=6),
                                            dbc.Col(_build_graph_panel("banking-ratios-nim-cir-graph", "Évolution NIM & Coeff. Exploitation (%)", "gold"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-ratios-roa-bank-graph", "ROA par Banque (année sélectionnée)", "green", "chart-wrap tall graph-container"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-ratios-cir-bank-graph", "Coeff. Exploitation par Banque (%)", "red", "chart-wrap tall graph-container"), xl=6),
                                        ],
                                        class_name="g-4",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="🏆 Classement",
                                tab_id="banking-tab-ranking",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-ranking-assets-graph", "Top Banques — Total Actif (Mds FCFA)", "", "chart-wrap tall graph-container"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-ranking-pnb-graph", "Top Banques — PNB (Mds FCFA)", "green", "chart-wrap tall graph-container"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Card(
                                        [
                                            html.Div([html.Span(className="dot gold"), "Tableau de Classement Complet"], className="card-title"),
                                            _build_ranking_table(),
                                        ],
                                        class_name="card",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="⚖️ Comparaison",
                                tab_id="banking-tab-comparison",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    dbc.Card(
                                        [
                                            html.Div([html.Span(className="dot"), "Sélectionner les banques à comparer (max 6)"], className="card-title"),
                                            html.Div(
                                                [
                                                    html.Label("Banques"),
                                                    dcc.Dropdown(
                                                        id="banking-compare-bank-selector",
                                                        options=[{"label": option["label"], "value": option["value"]} for option in bank_options if option["value"] != ALL_FILTER_VALUE],
                                                        value=[],
                                                        multi=True,
                                                        placeholder="Choisir jusqu'à 6 banques",
                                                        className="banking-select",
                                                    ),
                                                ],
                                                className="compare-select",
                                            ),
                                            html.Div(id="banking-compare-helper", className="ratio-desc"),
                                        ],
                                        class_name="card mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-compare-evolution-graph", "Évolution comparée (Mds FCFA)", "", "chart-wrap tall graph-container"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-compare-radar-graph", "Radar multi-indicateurs (dernière année disponible)", "gold", "chart-wrap tall graph-container"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-compare-direct-graph", "Comparaison directe (année sélectionnée)", "green"), xl=12),
                                        ],
                                        class_name="g-4",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="🔍 Analyse Banque",
                                tab_id="banking-tab-bank-analysis",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    html.Div(
                                        [
                                            html.Div(id="banking-analysis-bank-title", className="bank-name"),
                                            html.Div(
                                                "Selectionnez une banque pour voir son analyse detaillee.",
                                                id="banking-analysis-bank-meta",
                                                className="bank-meta",
                                            ),
                                            html.Div(
                                                [
                                                    _build_bank_focus_kpi("banking-analysis-kpi-assets", "Total actif"),
                                                    _build_bank_focus_kpi("banking-analysis-kpi-pnb", "PNB"),
                                                    _build_bank_focus_kpi("banking-analysis-kpi-result", "Resultat net"),
                                                    _build_bank_focus_kpi("banking-analysis-kpi-roe", "ROE"),
                                                ],
                                                className="bank-kpis",
                                            ),
                                        ],
                                        className="bank-header",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-analysis-assets-graph", "Évolution Total Actif", ""), xl=6),
                                            dbc.Col(_build_graph_panel("banking-analysis-pnb-graph", "PNB & Résultat Net", "green"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-analysis-result-graph", "Ratios ROA & ROE (%)", "purple"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-analysis-res-emp-graph", "Ressources & Emplois", "navy"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-analysis-cp-graph", "Capitaux Propres", "gold"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-analysis-network-graph", "Agences & Effectifs", "purple"), xl=6),
                                        ],
                                        class_name="g-4",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="🗺️ Carte & Réseau",
                                tab_id="banking-tab-map",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                dbc.Card(
                                                    [
                                                        html.Div([html.Span(className="dot"), "Légende & Stats Réseau"], className="card-title"),
                                                        html.Div(id="banking-map-legend-content"),
                                                    ],
                                                    class_name="card h-100",
                                                ),
                                                xl=3,
                                            ),
                                            dbc.Col(_build_graph_panel("banking-map-graph", "Présence Bancaire au Sénégal", "green"), xl=9),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-map-agencies-graph", "Agences par Banque", "gold", "chart-wrap tall graph-container"), xl=6),
                                            dbc.Col(_build_graph_panel("banking-map-staff-graph", "Effectifs par Banque", "purple", "chart-wrap tall graph-container"), xl=6),
                                        ],
                                        class_name="g-4 mb",
                                    ),
                                    dbc.Row(
                                        [
                                            dbc.Col(_build_graph_panel("banking-map-agencies-trend-graph", "Évolution Agences (Secteur)", ""), xl=6),
                                            dbc.Col(_build_graph_panel("banking-map-staff-trend-graph", "Évolution Effectifs (Secteur)", "purple"), xl=6),
                                        ],
                                        class_name="g-4",
                                    ),
                                ],
                            ),
                            dbc.Tab(
                                label="📋 Données",
                                tab_id="banking-tab-data-table",
                                tab_class_name="tab",
                                active_tab_class_name="active",
                                children=[
                                    dbc.Card(
                                        [
                                            html.Div(
                                                [
                                                    html.Span(className="dot"),
                                                    html.Span("Données complètes"),
                                                    html.Span(id="banking-data-count", style={"marginLeft": "auto", "fontSize": "11px", "fontWeight": "400", "color": "#7f8c8d"}),
                                                ],
                                                className="card-title",
                                            ),
                                            _build_raw_data_table(),
                                        ],
                                        class_name="card",
                                    ),
                                ],
                            ),
                        ],
                        active_tab="banking-tab-sector-view",
                        class_name="tabs no-print",
                    ),
                ],
                className="main",
            ),
            html.Footer([
                "Source : BCEAO · Base ",
                html.Em("banking_data"),
                " · ISM Dakar — M2 Big Data & Data Visualisation · 2015–2022",
            ]),
        ],
        className="banking-html-shell",
    )

# --- Visual system ----------------------------------------------------------
# The banking dashboard has its own premium navy/gold identity so all figures
# reuse the same palette and spacing rules.

PLOT_TEMPLATE = None
BANKING_BACKGROUND = "#ffffff"
BANKING_SURFACE = "#ffffff"
BANKING_TEXT = "#1c2833"
BANKING_MUTED = "#7f8c8d"
BANKING_NAVY = "#0f2b4c"
BANKING_BLUE = "#1a5276"
BANKING_MID = "#2980b9"
BANKING_GOLD = "#d4a017"
BANKING_GOLD_SOFT = "#e8b520"
BANKING_GREEN = "#27ae60"
BANKING_RED = "#e74c3c"
BANKING_PURPLE = "#8e44ad"
BANKING_BORDER = "#dce3ec"
BANKING_COLORWAY = [
    BANKING_BLUE,
    BANKING_GREEN,
    BANKING_GOLD,
    BANKING_RED,
    BANKING_PURPLE,
    "#16a085",
    "#d35400",
    BANKING_MID,
]
GROUP_COLOR_MAP = {
    "Groupes Locaux": BANKING_GREEN,
    "Groupes Regionaux": BANKING_MID,
    "Groupes Rgionaux": BANKING_MID,
    "Groupes Continentaux": BANKING_GOLD,
    "Groupes Internationaux": BANKING_PURPLE,
}
GROUP_CATEGORY_ORDER = [
    "Groupes Locaux",
    "Groupes Regionaux",
    "Groupes Rgionaux",
    "Groupes Continentaux",
    "Groupes Internationaux",
]
ASSET_STRUCTURE_COLOR_MAP = {
    "Emplois": BANKING_GOLD,
    "Autres actifs": BANKING_BLUE,
}
LIABILITY_STRUCTURE_COLOR_MAP = {
    "Ressources": BANKING_NAVY,
    "Capitaux propres": BANKING_PURPLE,
    "Autres passifs": "#94a3b8",
}
NETWORK_TIER_COLOR_MAP = {
    "Hub principal": BANKING_NAVY,
    "P?le r?gional": BANKING_MID,
    "Relais territorial": BANKING_GOLD,
}
NETWORK_TIER_ORDER = list(NETWORK_TIER_COLOR_MAP.keys())
METRIC_COLOR_MAP = {
    "bilan": BANKING_BLUE,
    "produit_net_bancaire": BANKING_GREEN,
    "resultat_net": BANKING_RED,
    "fonds_propres": BANKING_PURPLE,
    "agence": BANKING_BLUE,
    "effectif": BANKING_PURPLE,
}
COMPANY_ALIAS_MAP = {
    "ECOBANK": "ECOBANK SENEGAL",
    "ECOBANKSENEGAL": "ECOBANK SENEGAL",
    "ORABANKCOTEDIVOIRESUCCURSALEDUSENEGAL": "ORABANK",
    "ORABANKCOTEDIVOIRESUCCURSALEDUSENEGALSA": "ORABANK",
    "ORABANKCOTEDIVOIRESUCCURSALEDUSENEGALSUCCURSALE": "ORABANK",
}


# --- Data schema helpers ----------------------------------------------------
# Only the columns used by the dashboard are normalized and aggregated.

DOTATION_COLUMN = (
    "dotations_aux_amortissements_et_aux_depreciations_des_immobilisations_"
    "incorporelles_et_corporelles"
)
NUMERIC_COLUMNS = [
    "year",
    "annee",
    "emploi",
    "bilan",
    "ressources",
    "fonds_propres",
    "effectif",
    "agence",
    "compte",
    "interets_et_produits_assimiles",
    "interets_et_charges_assimilees",
    "produit_net_bancaire",
    "charges_generales_d_exploitation",
    DOTATION_COLUMN,
    "resultat_exploitation",
    "resultat_net",
]
SUMMARY_COLUMNS = [
    "emploi",
    "bilan",
    "ressources",
    "fonds_propres",
    "effectif",
    "agence",
    "compte",
    "interets_et_produits_assimiles",
    "interets_et_charges_assimilees",
    "produit_net_bancaire",
    "charges_generales_d_exploitation",
    DOTATION_COLUMN,
    "resultat_exploitation",
    "resultat_net",
]
SNAPSHOT_SUM_COLUMNS = ["bilan", "ressources", "fonds_propres", "compte"]
FLOW_SUM_COLUMNS = ["produit_net_bancaire", "resultat_exploitation", "resultat_net"]
AVERAGE_COLUMNS = ["effectif", "agence"]

SENEGAL_BANKING_HUBS = [
    {"city": "Dakar", "lat": 14.7167, "lon": -17.4677, "tier": "Hub principal", "weight": 0.34},
    {"city": "Thies", "lat": 14.7910, "lon": -16.9256, "tier": "P?le r?gional", "weight": 0.14},
    {"city": "Saint-Louis", "lat": 16.0326, "lon": -16.4818, "tier": "P?le r?gional", "weight": 0.10},
    {"city": "Kaolack", "lat": 14.1519, "lon": -16.0726, "tier": "P?le r?gional", "weight": 0.10},
    {"city": "Ziguinchor", "lat": 12.5681, "lon": -16.2733, "tier": "P?le r?gional", "weight": 0.08},
    {"city": "Touba", "lat": 14.8517, "lon": -15.8847, "tier": "P?le r?gional", "weight": 0.07},
    {"city": "Tambacounda", "lat": 13.7707, "lon": -13.6673, "tier": "Relais territorial", "weight": 0.06},
    {"city": "Kolda", "lat": 12.8833, "lon": -14.9500, "tier": "Relais territorial", "weight": 0.04},
    {"city": "Matam", "lat": 15.6559, "lon": -13.2554, "tier": "Relais territorial", "weight": 0.03},
    {"city": "Fatick", "lat": 14.3390, "lon": -16.4111, "tier": "Relais territorial", "weight": 0.02},
    {"city": "Diourbel", "lat": 14.6546, "lon": -16.2340, "tier": "Relais territorial", "weight": 0.02},
]


# --- Core math --------------------------------------------------------------


def _sum_with_min_count(series: pd.Series) -> float:
    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.dropna().empty:
        return pd.NA
    return float(numeric_series.sum(min_count=1))



def _mean_with_min_count(series: pd.Series) -> float:
    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.dropna().empty:
        return pd.NA
    return float(numeric_series.mean())



def _series_or_zero(dataframe: pd.DataFrame, column: str) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(0.0, index=dataframe.index, dtype="float64")
    return pd.to_numeric(dataframe[column], errors="coerce")



def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator_series = pd.to_numeric(numerator, errors="coerce")
    denominator_series = pd.to_numeric(denominator, errors="coerce")
    denominator_series = denominator_series.where(denominator_series != 0)
    return numerator_series.divide(denominator_series)



def _with_ratio_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    enriched = dataframe.copy()

    net_interest_income = _series_or_zero(enriched, "interets_et_produits_assimiles") - _series_or_zero(
        enriched, "interets_et_charges_assimilees"
    )
    operating_cost = _series_or_zero(enriched, "charges_generales_d_exploitation") + _series_or_zero(
        enriched, DOTATION_COLUMN
    )

    enriched["roa"] = _safe_divide(_series_or_zero(enriched, "resultat_net"), _series_or_zero(enriched, "bilan"))
    enriched["roe"] = _safe_divide(
        _series_or_zero(enriched, "resultat_net"),
        _series_or_zero(enriched, "fonds_propres"),
    )
    enriched["nim"] = _safe_divide(net_interest_income, _series_or_zero(enriched, "bilan"))
    enriched["coefficient_exploitation"] = _safe_divide(
        operating_cost,
        _series_or_zero(enriched, "produit_net_bancaire"),
    )
    enriched["emplois_ressources_ratio"] = _safe_divide(
        _series_or_zero(enriched, "emploi"),
        _series_or_zero(enriched, "ressources"),
    )
    enriched["other_assets"] = (
        _series_or_zero(enriched, "bilan") - _series_or_zero(enriched, "emploi")
    ).clip(lower=0)
    enriched["other_liabilities"] = (
        _series_or_zero(enriched, "bilan")
        - _series_or_zero(enriched, "ressources")
        - _series_or_zero(enriched, "fonds_propres")
    ).clip(lower=0)
    return enriched


# --- Data preparation -------------------------------------------------------


def _canonicalize_company_labels(prepared: pd.DataFrame) -> pd.DataFrame:
    if prepared.empty:
        return prepared

    def normalize_alias_key(value: object) -> str:
        normalized_value = unicodedata.normalize("NFKD", str(value).upper().strip())
        ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
        return re.sub(r"[^A-Z0-9]+", "", ascii_value)

    def choose_label(company_value: object, bank_name_value: object) -> str:
        company_label = str(company_value or "").strip().upper()
        bank_name_label = str(bank_name_value or "").strip().upper()
        alias_key = normalize_alias_key(bank_name_label or company_label)
        if alias_key in COMPANY_ALIAS_MAP:
            return COMPANY_ALIAS_MAP[alias_key]
        if company_label in {"", "BANQUE NON RENSEIGNEE"}:
            return bank_name_label or "BANQUE NON RENSEIGNEE"
        if bank_name_label in {"", "BANQUE NON RENSEIGNEE"}:
            return company_label
        return bank_name_label if len(bank_name_label) >= len(company_label) else company_label

    prepared["company"] = prepared["company"].fillna("Banque non renseignee").astype(str).str.upper().str.strip()
    prepared["bank_name"] = prepared["bank_name"].fillna(prepared["company"]).astype(str).str.upper().str.strip()
    prepared["company"] = [
        choose_label(company_value, bank_name_value)
        for company_value, bank_name_value in zip(prepared["company"], prepared["bank_name"], strict=False)
    ]
    prepared["bank_name"] = prepared["company"]

    if "sigle" in prepared.columns:
        prepared["sigle"] = prepared["sigle"].fillna("").astype(str).str.upper().str.strip()
        naming_frame = prepared.loc[prepared["sigle"].ne(""), ["sigle", "bank_name", "company"]].copy()
        if not naming_frame.empty:
            naming_frame["canonical_label"] = [
                choose_label(company_value, bank_name_value)
                for bank_name_value, company_value in zip(
                    naming_frame["bank_name"],
                    naming_frame["company"],
                    strict=False,
                )
            ]
            naming_frame["label_length"] = naming_frame["canonical_label"].str.len()
            canonical_by_sigle = (
                naming_frame.sort_values(["sigle", "label_length"], ascending=[True, False], kind="stable")
                .drop_duplicates(subset=["sigle"])
                .set_index("sigle")["canonical_label"]
                .to_dict()
            )
            prepared["company"] = prepared["sigle"].map(canonical_by_sigle).fillna(prepared["company"])
            prepared["bank_name"] = prepared["company"]

    return prepared



def _prepare_banking_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    prepared = dataframe.copy()
    if prepared.empty:
        return _with_ratio_columns(prepared)

    if "year" not in prepared.columns and "annee" in prepared.columns:
        prepared["year"] = prepared["annee"]
    if "company" not in prepared.columns and "bank_name" in prepared.columns:
        prepared["company"] = prepared["bank_name"]
    if "company" not in prepared.columns and "bank" in prepared.columns:
        prepared["company"] = prepared["bank"]
    if "bank_name" not in prepared.columns and "company" in prepared.columns:
        prepared["bank_name"] = prepared["company"]
    if "groupe_bancaire" not in prepared.columns:
        prepared["groupe_bancaire"] = "Non renseigne"

    prepared["groupe_bancaire"] = prepared["groupe_bancaire"].fillna("Non renseigne").astype(str).str.strip()
    prepared = _canonicalize_company_labels(prepared)

    for column in NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    if "year" in prepared.columns:
        prepared["year"] = prepared["year"].astype("Int64")

    return _with_ratio_columns(prepared)



def _filter_banking_dataframe(
    dataframe: pd.DataFrame,
    selected_year: object,
    selected_group: object,
    selected_bank: object,
) -> pd.DataFrame:
    filtered = dataframe.copy()

    if "year" in filtered.columns and selected_year not in (None, ALL_FILTER_VALUE):
        filtered = filtered[filtered["year"] == selected_year]
    if "groupe_bancaire" in filtered.columns and selected_group not in (None, ALL_FILTER_VALUE):
        filtered = filtered[filtered["groupe_bancaire"] == selected_group]
    if "company" in filtered.columns and selected_bank not in (None, ALL_FILTER_VALUE):
        filtered = filtered[filtered["company"] == selected_bank]

    return filtered



def _select_latest_year_snapshot(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "year" not in dataframe.columns:
        return dataframe.copy()

    with_years = dataframe.dropna(subset=["year"]).copy()
    if with_years.empty:
        return dataframe.copy()

    latest_year = with_years["year"].max()
    return with_years[with_years["year"] == latest_year].copy()



def _aggregate_company_metrics(
    dataframe: pd.DataFrame,
    sum_columns: list[str],
    average_columns: list[str],
) -> pd.DataFrame:
    if dataframe.empty or "company" not in dataframe.columns:
        return pd.DataFrame(columns=["company", *sum_columns, *average_columns])

    aggregation_map: dict[str, Any] = {}
    for column in sum_columns:
        if column in dataframe.columns:
            aggregation_map[column] = _sum_with_min_count
    for column in average_columns:
        if column in dataframe.columns:
            aggregation_map[column] = _mean_with_min_count

    if not aggregation_map:
        return (
            dataframe[["company"]]
            .drop_duplicates()
            .sort_values("company", kind="stable")
            .reset_index(drop=True)
        )

    aggregated = (
        dataframe.groupby("company", dropna=True, as_index=False)
        .agg(aggregation_map)
        .sort_values("company", kind="stable")
        .reset_index(drop=True)
    )

    for column in [*sum_columns, *average_columns]:
        if column in aggregated.columns:
            aggregated[column] = pd.to_numeric(aggregated[column], errors="coerce")

    return aggregated



def _aggregate_by_company(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "company" not in dataframe.columns:
        return pd.DataFrame(columns=["company", *SNAPSHOT_SUM_COLUMNS, *FLOW_SUM_COLUMNS, *AVERAGE_COLUMNS])

    latest_year_snapshot = _select_latest_year_snapshot(dataframe)
    snapshot_summary = _aggregate_company_metrics(
        latest_year_snapshot,
        sum_columns=SNAPSHOT_SUM_COLUMNS,
        average_columns=AVERAGE_COLUMNS,
    )
    flow_summary = _aggregate_company_metrics(
        dataframe,
        sum_columns=FLOW_SUM_COLUMNS,
        average_columns=[],
    )
    aggregated = snapshot_summary.merge(flow_summary, on="company", how="outer")
    return aggregated.sort_values("company", kind="stable").reset_index(drop=True)



def _aggregate_frame(dataframe: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if dataframe.empty or any(column not in dataframe.columns for column in group_columns):
        return pd.DataFrame(columns=[*group_columns, *SUMMARY_COLUMNS, "roa", "roe", "nim", "coefficient_exploitation"])

    aggregate_columns = [column for column in SUMMARY_COLUMNS if column in dataframe.columns]
    aggregated = (
        dataframe.groupby(group_columns, dropna=True, as_index=False)[aggregate_columns]
        .sum(min_count=1)
        .reset_index(drop=True)
    )
    return _with_ratio_columns(aggregated)



def _aggregate_snapshot_by_company(snapshot_frame: pd.DataFrame) -> pd.DataFrame:
    aggregated = _aggregate_frame(snapshot_frame, ["company", "groupe_bancaire"])
    if "bilan" in aggregated.columns:
        aggregated = aggregated.sort_values("bilan", ascending=False, kind="stable")
    return aggregated.reset_index(drop=True)



def _aggregate_by_group(snapshot_frame: pd.DataFrame) -> pd.DataFrame:
    aggregated = _aggregate_frame(snapshot_frame, ["groupe_bancaire"])
    if "bilan" in aggregated.columns:
        aggregated = aggregated.sort_values("bilan", ascending=False, kind="stable")
    return aggregated.reset_index(drop=True)



def _aggregate_by_year(dataframe: pd.DataFrame) -> pd.DataFrame:
    aggregated = _aggregate_frame(dataframe, ["year"])
    if "year" in aggregated.columns:
        aggregated["year"] = aggregated["year"].astype(int)
        aggregated = aggregated.sort_values("year", kind="stable")
    if not dataframe.empty and {"year", "company"}.issubset(dataframe.columns):
        counts = (
            dataframe.dropna(subset=["year"]).groupby("year")["company"].nunique().reset_index(name="bank_count")
        )
        aggregated = aggregated.merge(counts, on="year", how="left")
    return aggregated.reset_index(drop=True)



def _aggregate_by_bank_year(dataframe: pd.DataFrame) -> pd.DataFrame:
    aggregated = _aggregate_frame(dataframe, ["year", "company", "groupe_bancaire"])
    if "year" in aggregated.columns:
        aggregated["year"] = aggregated["year"].astype(int)
    return aggregated.sort_values(["company", "year"], kind="stable").reset_index(drop=True)



def _format_kpi_metric(
    dataframe: pd.DataFrame,
    metric_column: str,
    *,
    snapshot_latest_year: bool = False,
    suffix: str = " FCFA",
) -> str:
    source_frame = _select_latest_year_snapshot(dataframe) if snapshot_latest_year else dataframe
    if source_frame.empty or metric_column not in source_frame.columns:
        return "N/A"
    return format_number(source_frame[metric_column].sum(min_count=1), suffix=suffix)



def _format_count(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{int(round(float(value))):,}".replace(",", " ")


def _format_ratio_value(value: object, *, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value) * 100:.{decimals}f}%"


def _build_sector_ratio_snapshot(snapshot_frame: pd.DataFrame) -> pd.Series:
    if snapshot_frame.empty:
        return pd.Series(dtype="object")

    scoped_frame = snapshot_frame.copy()
    scoped_frame["scope"] = "Secteur"
    sector_ratio_frame = _aggregate_frame(scoped_frame, ["scope"])
    if sector_ratio_frame.empty:
        return pd.Series(dtype="object")
    return sector_ratio_frame.iloc[0]


def _decode_plotly_array(value: object) -> object:
    if isinstance(value, dict) and set(value.keys()) == {"dtype", "bdata"}:
        decoded = base64.b64decode(value["bdata"])
        return np.frombuffer(decoded, dtype=np.dtype(value["dtype"])).tolist()
    if isinstance(value, dict):
        return {key: _decode_plotly_array(nested_value) for key, nested_value in value.items()}
    if isinstance(value, list):
        return [_decode_plotly_array(item) for item in value]
    return value


def _serialize_figure(figure: go.Figure) -> dict[str, object]:
    return _decode_plotly_array(figure.to_plotly_json())


# --- Generic chart styling --------------------------------------------------


def _empty_figure(title: str, message: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 15, "color": BANKING_MUTED},
    )
    return _apply_banking_theme(figure, title)



def _apply_banking_theme(
    figure: go.Figure,
    title: str,
    *,
    x_title: str | None = None,
    y_title: str | None = None,
    height: int = GRAPH_HEIGHT,
    hovermode: str = "x unified",
) -> dict[str, object]:
    figure.update_layout(
        template=PLOT_TEMPLATE,
        paper_bgcolor=BANKING_BACKGROUND,
        plot_bgcolor=BANKING_BACKGROUND,
        colorway=BANKING_COLORWAY,
        font={"color": BANKING_TEXT, "family": "Segoe UI, system-ui, sans-serif"},
        margin={"l": 36, "r": 18, "t": 26, "b": 30},
        height=height,
        autosize=True,
        hovermode=hovermode,
        uirevision="banking-static",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "font": {"size": 11}},
        hoverlabel={"bgcolor": "#ffffff", "font": {"color": BANKING_TEXT}},
    )
    figure.update_xaxes(
        title=x_title,
        gridcolor="#edf0f2",
        zeroline=False,
        showline=False,
        automargin=True,
        ticks="outside",
        tickfont={"color": BANKING_MUTED},
    )
    figure.update_yaxes(
        title=y_title,
        gridcolor="#edf0f2",
        zeroline=False,
        showline=False,
        automargin=True,
        ticks="outside",
        tickfont={"color": BANKING_MUTED},
    )
    return _serialize_figure(figure)

# --- Figure builders: sector overview --------------------------------------


def _build_metric_line_figure(yearly: pd.DataFrame, metric_column: str, title: str, y_title: str) -> go.Figure:
    if yearly.empty or metric_column not in yearly.columns:
        return _empty_figure(title, "Aucune donnee disponible pour ce graphique.")

    line_color = METRIC_COLOR_MAP.get(metric_column, BANKING_BLUE)
    figure = px.line(
        yearly,
        x="year",
        y=metric_column,
        markers=True,
        line_shape="spline",
    )
    figure.update_traces(line={"width": 2.5, "color": line_color}, marker={"size": 6, "color": line_color})
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, title, x_title="Annee", y_title=y_title)



def _build_sector_resources_vs_emplois_figure(yearly: pd.DataFrame) -> go.Figure:
    if yearly.empty or not {"ressources", "emploi"}.issubset(yearly.columns):
        return _empty_figure("Ressources vs emplois", "Aucune structure sectorielle disponible.")

    figure = go.Figure()
    figure.add_bar(x=yearly["year"], y=yearly["ressources"], name="Ressources", marker_color=BANKING_NAVY)
    figure.add_bar(x=yearly["year"], y=yearly["emploi"], name="Emplois", marker_color=BANKING_GOLD)
    figure.update_layout(barmode="group")
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, "Ressources vs emplois", x_title="Annee", y_title="FCFA")



def _build_group_share_figure(group_snapshot: pd.DataFrame) -> go.Figure:
    if group_snapshot.empty or "bilan" not in group_snapshot.columns:
        return _empty_figure("Repartition par groupe bancaire", "Aucune repartition groupe disponible.")

    figure = px.pie(
        group_snapshot,
        names="groupe_bancaire",
        values="bilan",
        hole=0.55,
        color="groupe_bancaire",
        color_discrete_map=GROUP_COLOR_MAP,
    )
    figure.update_traces(textposition="inside", textinfo="percent+label")
    return _apply_banking_theme(figure, "Repartition par groupe bancaire", hovermode="closest")


# --- Figure builders: balance structure ------------------------------------


def _build_asset_structure_figure(snapshot_frame: pd.DataFrame) -> go.Figure:
    if snapshot_frame.empty:
        return _empty_figure("Structure actif", "Aucun snapshot actif disponible.")

    structure = pd.DataFrame(
        {
            "poste": ["Emplois", "Autres actifs"],
            "value": [
                _series_or_zero(snapshot_frame, "emploi").sum(min_count=1),
                _series_or_zero(snapshot_frame, "other_assets").sum(min_count=1),
            ],
        }
    )
    figure = px.pie(
        structure,
        names="poste",
        values="value",
        hole=0.55,
        color="poste",
        color_discrete_map=ASSET_STRUCTURE_COLOR_MAP,
    )
    return _apply_banking_theme(figure, "Structure actif", hovermode="closest")



def _build_liability_structure_figure(snapshot_frame: pd.DataFrame) -> go.Figure:
    if snapshot_frame.empty:
        return _empty_figure("Structure passif", "Aucun snapshot passif disponible.")

    structure = pd.DataFrame(
        {
            "poste": ["Ressources", "Capitaux propres", "Autres passifs"],
            "value": [
                _series_or_zero(snapshot_frame, "ressources").sum(min_count=1),
                _series_or_zero(snapshot_frame, "fonds_propres").sum(min_count=1),
                _series_or_zero(snapshot_frame, "other_liabilities").sum(min_count=1),
            ],
        }
    )
    figure = px.pie(
        structure,
        names="poste",
        values="value",
        hole=0.55,
        color="poste",
        color_discrete_map=LIABILITY_STRUCTURE_COLOR_MAP,
    )
    return _apply_banking_theme(figure, "Structure passif", hovermode="closest")



def _build_client_balance_figure(snapshot_banks: pd.DataFrame) -> go.Figure:
    if snapshot_banks.empty or not {"emploi", "ressources"}.issubset(snapshot_banks.columns):
        return _empty_figure("Creances vs dettes clientele", "Aucune comparaison emplois / ressources disponible.")

    top_frame = snapshot_banks.nlargest(10, "bilan" if "bilan" in snapshot_banks.columns else "emploi").copy()
    melted = top_frame.melt(
        id_vars=["company"],
        value_vars=["emploi", "ressources"],
        var_name="metric",
        value_name="value",
    )
    melted["metric"] = melted["metric"].map({"emploi": "Creances clientele", "ressources": "Dettes clientele"})
    figure = px.bar(
        melted,
        x="value",
        y="company",
        color="metric",
        orientation="h",
        barmode="group",
        color_discrete_sequence=[BANKING_GOLD, "#82aaff"],
    )
    figure.update_xaxes(tickformat=",")
    return _apply_banking_theme(figure, "Creances vs dettes clientele", x_title="FCFA", y_title="Banque", hovermode="closest")



def _build_ratio_emplois_ressources_figure(snapshot_banks: pd.DataFrame) -> go.Figure:
    if snapshot_banks.empty or "emplois_ressources_ratio" not in snapshot_banks.columns:
        return _empty_figure("Ratio emplois / ressources", "Aucun ratio emplois / ressources disponible.")

    ordered = snapshot_banks.sort_values("emplois_ressources_ratio", ascending=False, kind="stable")
    figure = px.bar(
        ordered,
        x="company",
        y="emplois_ressources_ratio",
        color="groupe_bancaire",
        color_discrete_map=GROUP_COLOR_MAP,
        category_orders={"groupe_bancaire": GROUP_CATEGORY_ORDER},
    )
    figure.update_xaxes(tickangle=-22)
    figure.update_yaxes(tickformat=".0%")
    return _apply_banking_theme(
        figure,
        "Ratio emplois / ressources",
        x_title="Banque",
        y_title="Ratio",
        hovermode="closest",
    )


# --- Figure builders: ratios ------------------------------------------------


def _build_dual_ratio_line_figure(
    yearly: pd.DataFrame,
    first_column: str,
    second_column: str,
    title: str,
    first_label: str,
    second_label: str,
) -> go.Figure:
    if yearly.empty or not {first_column, second_column}.issubset(yearly.columns):
        return _empty_figure(title, "Aucune serie de ratios disponible.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=yearly["year"],
            y=yearly[first_column],
            mode="lines+markers",
            name=first_label,
            line={"width": 2.5, "color": BANKING_BLUE},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=yearly["year"],
            y=yearly[second_column],
            mode="lines+markers",
            name=second_label,
            line={"width": 2.5, "color": BANKING_GOLD},
        )
    )
    figure.update_yaxes(tickformat=".1%")
    return _apply_banking_theme(figure, title, x_title="Annee", y_title="Ratio")



def _build_ratio_bank_figure(snapshot_banks: pd.DataFrame, ratio_column: str, title: str) -> go.Figure:
    if snapshot_banks.empty or ratio_column not in snapshot_banks.columns:
        return _empty_figure(title, "Aucun ratio bancaire disponible.")

    ordered = snapshot_banks.sort_values(ratio_column, ascending=False, kind="stable")
    figure = px.bar(
        ordered,
        x="company",
        y=ratio_column,
        color="groupe_bancaire",
        color_discrete_map=GROUP_COLOR_MAP,
        category_orders={"groupe_bancaire": GROUP_CATEGORY_ORDER},
    )
    figure.update_xaxes(tickangle=-22)
    figure.update_yaxes(tickformat=".1%")
    return _apply_banking_theme(figure, title, x_title="Banque", y_title="Ratio", hovermode="closest")


# --- Figure builders: rankings ---------------------------------------------


def _build_top_banks_figure(snapshot_banks: pd.DataFrame, metric_column: str, title: str) -> go.Figure:
    if snapshot_banks.empty or metric_column not in snapshot_banks.columns:
        return _empty_figure(title, "Aucun classement disponible pour cette mesure.")

    top_frame = snapshot_banks.nlargest(10, metric_column).copy().sort_values(metric_column, ascending=True)
    figure = px.bar(
        top_frame,
        x=metric_column,
        y="company",
        color="groupe_bancaire",
        orientation="h",
        color_discrete_map=GROUP_COLOR_MAP,
        category_orders={"groupe_bancaire": GROUP_CATEGORY_ORDER},
    )
    figure.update_xaxes(tickformat=",")
    return _apply_banking_theme(figure, title, x_title="Valeur", y_title="Banque", hovermode="closest")



def _build_ranking_table_data(snapshot_banks: pd.DataFrame) -> list[dict[str, object]]:
    if snapshot_banks.empty:
        return []

    ranking_columns = [
        "company",
        "groupe_bancaire",
        "bilan",
        "produit_net_bancaire",
        "resultat_net",
        "fonds_propres",
        "roa",
        "roe",
    ]
    ranking_frame = snapshot_banks.copy()
    for column in ranking_columns:
        if column not in ranking_frame.columns:
            ranking_frame[column] = pd.NA

    ranking_frame = ranking_frame[ranking_columns].sort_values("bilan", ascending=False, kind="stable")
    return ranking_frame.to_dict("records")

# --- Figure builders: comparison -------------------------------------------


def _normalize_compare_selection(
    snapshot_banks: pd.DataFrame,
    selected_compare_banks: list[str] | None,
    selected_bank: object,
) -> list[str]:
    available_banks = snapshot_banks.get("company", pd.Series(dtype="object")).dropna().astype(str).tolist()
    chosen = [bank for bank in (selected_compare_banks or []) if bank in available_banks]

    if selected_bank not in (None, ALL_FILTER_VALUE) and selected_bank in available_banks and selected_bank not in chosen:
        chosen.insert(0, str(selected_bank))

    if not chosen:
        chosen = available_banks[: min(3, len(available_banks))]

    return chosen[:6]



def _build_compare_evolution_figure(compare_history: pd.DataFrame) -> go.Figure:
    if compare_history.empty:
        return _empty_figure("Evolution comparee", "Selectionne au moins une banque pour activer la comparaison.")

    metrics = [
        ("bilan", "Actif total"),
        ("produit_net_bancaire", "PNB"),
        ("resultat_net", "Resultat net"),
    ]
    figure = go.Figure()
    metric_trace_indexes: list[list[int]] = []

    for metric_index, (metric_column, _) in enumerate(metrics):
        indexes: list[int] = []
        for company, company_frame in compare_history.groupby("company"):
            figure.add_trace(
                go.Scatter(
                    x=company_frame["year"],
                    y=company_frame[metric_column],
                    mode="lines+markers",
                    name=company,
                    visible=metric_index == 0,
                    legendgroup=company,
                )
            )
            indexes.append(len(figure.data) - 1)
        metric_trace_indexes.append(indexes)

    buttons = []
    total_traces = len(figure.data)
    for metric_index, (_, metric_label) in enumerate(metrics):
        visibility = [False] * total_traces
        for trace_index in metric_trace_indexes[metric_index]:
            visibility[trace_index] = True
        buttons.append(
            {
                "label": metric_label,
                "method": "update",
                "args": [{"visible": visibility}],
            }
        )

    figure.update_layout(
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "x": 0.01,
                "y": 1.18,
                "buttons": buttons,
                "showactive": True,
            }
        ]
    )
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, "Evolution comparee", x_title="Annee", y_title="Valeur")



def _build_radar_figure(compare_snapshot: pd.DataFrame) -> go.Figure:
    if compare_snapshot.empty:
        return _empty_figure("Radar multi-indicateurs", "Aucune banque comparee sur le snapshot courant.")

    metrics = {
        "Actif": "bilan",
        "PNB": "produit_net_bancaire",
        "Resultat": "resultat_net",
        "ROA": "roa",
        "ROE": "roe",
    }
    normalized = compare_snapshot[["company", *metrics.values()]].copy().fillna(0)

    for column in metrics.values():
        minimum = normalized[column].min()
        maximum = normalized[column].max()
        if minimum == maximum:
            normalized[column] = 1.0
        else:
            normalized[column] = 0.25 + 0.75 * ((normalized[column] - minimum) / (maximum - minimum))

    figure = go.Figure()
    labels = list(metrics.keys())
    for _, row in normalized.iterrows():
        values = [row[column] for column in metrics.values()]
        values.append(values[0])
        figure.add_trace(
            go.Scatterpolar(
                r=values,
                theta=[*labels, labels[0]],
                fill="toself",
                name=row["company"],
            )
        )

    figure.update_layout(
        polar={
            "bgcolor": BANKING_BACKGROUND,
            "radialaxis": {"visible": True, "range": [0, 1.2], "gridcolor": "rgba(148, 163, 184, 0.12)"},
            "angularaxis": {"gridcolor": "rgba(148, 163, 184, 0.12)"},
        }
    )
    return _apply_banking_theme(figure, "Radar multi-indicateurs", hovermode="closest")



def _build_direct_comparison_figure(compare_snapshot: pd.DataFrame) -> go.Figure:
    if compare_snapshot.empty:
        return _empty_figure("Comparaison directe", "Aucune banque comparee pour la comparaison directe.")

    direct_frame = compare_snapshot[["company", "bilan", "produit_net_bancaire", "resultat_net"]].melt(
        id_vars="company",
        var_name="metric",
        value_name="value",
    )
    direct_frame["metric"] = direct_frame["metric"].map(
        {
            "bilan": "Actif total",
            "produit_net_bancaire": "PNB",
            "resultat_net": "Resultat net",
        }
    )
    figure = px.bar(
        direct_frame,
        x="metric",
        y="value",
        color="company",
        barmode="group",
        color_discrete_sequence=BANKING_COLORWAY,
    )
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, "Comparaison directe", x_title="Indicateur", y_title="Valeur")


# --- Figure builders: bank focus -------------------------------------------


def _resolve_focus_bank(snapshot_banks: pd.DataFrame, selected_bank: object) -> str | None:
    if snapshot_banks.empty or "company" not in snapshot_banks.columns:
        return None
    if selected_bank not in (None, ALL_FILTER_VALUE):
        return str(selected_bank)
    return snapshot_banks.iloc[0]["company"]



def _build_bank_history_figure(bank_history: pd.DataFrame, metric_column: str, title: str) -> go.Figure:
    if bank_history.empty or metric_column not in bank_history.columns:
        return _empty_figure(title, "Aucun historique disponible pour cette banque.")

    line_color = METRIC_COLOR_MAP.get(metric_column, BANKING_BLUE)
    figure = px.line(bank_history, x="year", y=metric_column, markers=True, line_shape="spline")
    figure.update_traces(line={"width": 2.5, "color": line_color}, marker={"size": 6, "color": line_color})
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, title, x_title="Annee", y_title="Valeur")


def _build_bank_res_emp_figure(bank_history: pd.DataFrame) -> go.Figure:
    if bank_history.empty or ("ressources" not in bank_history.columns and "emploi" not in bank_history.columns):
        return _empty_figure("Ressources & Emplois", "Aucun historique disponible pour cette banque.")

    figure = go.Figure()
    if "ressources" in bank_history.columns:
        figure.add_trace(go.Scatter(
            x=bank_history["year"], y=bank_history["ressources"],
            mode="lines+markers", name="Ressources",
            line={"width": 2.5, "color": BANKING_BLUE},
            marker={"size": 6},
        ))
    if "emploi" in bank_history.columns:
        figure.add_trace(go.Scatter(
            x=bank_history["year"], y=bank_history["emploi"],
            mode="lines+markers", name="Emplois",
            line={"width": 2.5, "color": BANKING_GREEN},
            marker={"size": 6},
        ))
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, "Ressources & Emplois", x_title="Annee", y_title="FCFA")


def _build_bank_cp_figure(bank_history: pd.DataFrame) -> go.Figure:
    if bank_history.empty or "fonds_propres" not in bank_history.columns:
        return _empty_figure("Capitaux Propres", "Aucun historique de capitaux propres disponible.")

    figure = px.bar(bank_history, x="year", y="fonds_propres", color_discrete_sequence=[BANKING_PURPLE])
    figure.update_yaxes(tickformat=",")
    return _apply_banking_theme(figure, "Capitaux Propres", x_title="Annee", y_title="FCFA")


def _build_bank_network_figure(bank_history: pd.DataFrame) -> go.Figure:
    if bank_history.empty or ("agence" not in bank_history.columns and "effectif" not in bank_history.columns):
        return _empty_figure("Agences & Effectifs", "Aucun historique reseau disponible pour cette banque.")

    figure = go.Figure()
    if "agence" in bank_history.columns:
        figure.add_trace(go.Bar(
            x=bank_history["year"], y=bank_history["agence"],
            name="Agences", marker_color=BANKING_GOLD,
        ))
    if "effectif" in bank_history.columns:
        figure.add_trace(go.Scatter(
            x=bank_history["year"], y=bank_history["effectif"],
            mode="lines+markers", name="Effectifs",
            line={"width": 2.5, "color": BANKING_PURPLE},
            marker={"size": 6},
            yaxis="y2",
        ))
    figure.update_layout(yaxis2={"overlaying": "y", "side": "right", "showgrid": False})
    return _apply_banking_theme(figure, "Agences & Effectifs", x_title="Annee", y_title="Agences")


# --- Figure builders: map and network --------------------------------------


def _build_presence_frame(snapshot_banks: pd.DataFrame) -> pd.DataFrame:
    if snapshot_banks.empty:
        return snapshot_banks.copy()

    total_banks = int(snapshot_banks["company"].nunique()) if "company" in snapshot_banks.columns else 0
    total_agencies = float(_series_or_zero(snapshot_banks, "agence").sum(min_count=1) or 0)
    total_staff = float(_series_or_zero(snapshot_banks, "effectif").sum(min_count=1) or 0)

    if total_banks <= 1:
        dakar = SENEGAL_BANKING_HUBS[0]
        return pd.DataFrame(
            [
                {
                    "hub_city": dakar["city"],
                    "lat": dakar["lat"],
                    "lon": dakar["lon"],
                    "tier": dakar["tier"],
                    "coverage_weight": 1.0,
                    "visible_banks": total_banks,
                    "estimated_agencies": int(round(total_agencies)) if total_agencies else 0,
                    "estimated_staff": int(round(total_staff)) if total_staff else 0,
                    "scope_note": "Localisation d?taill?e indisponible pour le p?rim?tre s?lectionn?.",
                }
            ]
        )

    hub_rows: list[dict[str, object]] = []
    for hub in SENEGAL_BANKING_HUBS:
        estimated_agencies = int(round(total_agencies * hub["weight"])) if total_agencies else 0
        estimated_staff = int(round(total_staff * hub["weight"])) if total_staff else 0
        visible_banks = int(round(total_banks * hub["weight"])) if total_banks else 0
        if hub["city"] == "Dakar":
            visible_banks = max(visible_banks, 1)
        if not any([estimated_agencies, estimated_staff, visible_banks]):
            continue
        hub_rows.append(
            {
                "hub_city": hub["city"],
                "lat": hub["lat"],
                "lon": hub["lon"],
                "tier": hub["tier"],
                "coverage_weight": hub["weight"],
                "visible_banks": visible_banks,
                "estimated_agencies": estimated_agencies,
                "estimated_staff": estimated_staff,
                "scope_note": "Projection indicative bas?e sur les volumes agr?g?s visibles.",
            }
        )

    return pd.DataFrame(hub_rows)


def _build_presence_map(snapshot_banks: pd.DataFrame) -> go.Figure:
    if snapshot_banks.empty:
        return _empty_figure("Projection r?seau", "Aucune pr?sence r?seau ? projeter.")

    map_frame = _build_presence_frame(snapshot_banks)
    if map_frame.empty:
        return _empty_figure("Projection r?seau", "Aucune projection r?seau disponible.")

    map_frame["map_size"] = (
        pd.to_numeric(map_frame.get("estimated_agencies", 1), errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(float)
    )
    map_frame["map_size"] = map_frame["map_size"].where(map_frame["map_size"] > 0, 1.0)
    figure = px.scatter_geo(
        map_frame,
        lat="lat",
        lon="lon",
        size="map_size",
        color="tier",
        hover_name="hub_city",
        hover_data={
            "tier": True,
            "hub_city": True,
            "visible_banks": ":,.0f",
            "estimated_agencies": ":,.0f",
            "estimated_staff": ":,.0f",
            "scope_note": True,
            "map_size": False,
            "lat": False,
            "lon": False,
        },
        color_discrete_map=NETWORK_TIER_COLOR_MAP,
        category_orders={"tier": NETWORK_TIER_ORDER},
        size_max=30,
    )
    figure.update_traces(
        marker={"line": {"color": "rgba(15, 43, 76, 0.24)", "width": 1.2}},
        selector={"mode": "markers"},
    )
    figure.update_geos(
        scope="africa",
        showland=True,
        landcolor="#eff4f8",
        showcountries=True,
        countrycolor="rgba(15, 43, 76, 0.18)",
        showocean=True,
        oceancolor="#dfeef8",
        showcoastlines=True,
        coastlinecolor="rgba(15, 43, 76, 0.22)",
        lataxis_range=[12.0, 17.5],
        lonaxis_range=[-18.5, -11.0],
        center={"lat": 14.5, "lon": -14.5},
        projection_scale=8,
    )
    return _apply_banking_theme(figure, "Projection r?seau", hovermode="closest", height=420)


def _build_agencies_bank_figure(snapshot_banks: pd.DataFrame) -> go.Figure:
    if snapshot_banks.empty or "agence" not in snapshot_banks.columns:
        return _empty_figure("Agences par banque", "Aucune donnee d'agences disponible.")

    top_frame = snapshot_banks.nlargest(10, "agence")
    figure = px.bar(
        top_frame,
        x="company",
        y="agence",
        color="groupe_bancaire",
        color_discrete_map=GROUP_COLOR_MAP,
        category_orders={"groupe_bancaire": GROUP_CATEGORY_ORDER},
    )
    figure.update_xaxes(tickangle=-22)
    return _apply_banking_theme(figure, "Agences par banque", x_title="Banque", y_title="Agences", hovermode="closest")



def _build_staff_bank_figure(snapshot_banks: pd.DataFrame) -> go.Figure:
    if snapshot_banks.empty or "effectif" not in snapshot_banks.columns:
        return _empty_figure("Effectifs par banque", "Aucune donnee d'effectif disponible.")

    top_frame = snapshot_banks.nlargest(10, "effectif")
    figure = px.bar(
        top_frame,
        x="company",
        y="effectif",
        color="groupe_bancaire",
        color_discrete_map=GROUP_COLOR_MAP,
        category_orders={"groupe_bancaire": GROUP_CATEGORY_ORDER},
    )
    figure.update_xaxes(tickangle=-22)
    return _apply_banking_theme(figure, "Effectifs par banque", x_title="Banque", y_title="Effectif", hovermode="closest")



def _build_agencies_trend_figure(yearly: pd.DataFrame) -> go.Figure:
    if yearly.empty or "agence" not in yearly.columns:
        return _empty_figure("Evolution agences", "Aucune evolution d'agences disponible.")

    figure = px.area(yearly, x="year", y="agence")
    figure.update_traces(line={"width": 2, "color": BANKING_BLUE}, fillcolor="rgba(26, 82, 118, 0.12)")
    return _apply_banking_theme(figure, "Evolution agences", x_title="Annee", y_title="Agences")


def _build_staff_trend_figure(yearly: pd.DataFrame) -> go.Figure:
    if yearly.empty or "effectif" not in yearly.columns:
        return _empty_figure("Evolution effectifs", "Aucune evolution d'effectifs disponible.")

    figure = px.area(yearly, x="year", y="effectif")
    figure.update_traces(line={"width": 2, "color": BANKING_PURPLE}, fillcolor="rgba(142, 68, 173, 0.12)")
    return _apply_banking_theme(figure, "Evolution effectifs", x_title="Annee", y_title="Effectif")


def _build_map_legend_content(snapshot_banks: pd.DataFrame) -> html.Div:
    if snapshot_banks.empty:
        return html.Div("Aucune donnee reseau disponible.", className="ratio-desc")

    total_banks = int(snapshot_banks["company"].nunique()) if "company" in snapshot_banks.columns else 0
    agencies_series = snapshot_banks["agence"] if "agence" in snapshot_banks.columns else pd.Series(dtype="float64")
    staff_series = snapshot_banks["effectif"] if "effectif" in snapshot_banks.columns else pd.Series(dtype="float64")
    total_agencies = _format_count(pd.to_numeric(agencies_series, errors="coerce").sum(min_count=1))
    total_staff = _format_count(pd.to_numeric(staff_series, errors="coerce").sum(min_count=1))

    legend_items = []
    for tier_name in NETWORK_TIER_ORDER:
        legend_items.append(
            html.Div(
                [
                    html.Span(
                        className="bilan-leg-dot",
                        style={"background": NETWORK_TIER_COLOR_MAP[tier_name]},
                    ),
                    html.Span(tier_name),
                ],
                className="bilan-leg-item",
            )
        )

    return html.Div(
        [
            html.Div("Couverture reseau", className="ratio-name"),
            html.Div(f"{total_banks} banques", className="ratio-value"),
            html.Div("Lecture indicative du maillage national sur des hubs bancaires de r?f?rence.", className="ratio-desc"),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Agences", className="kpi-label"),
                            html.Div(total_agencies, className="ratio-value"),
                        ],
                        className="ratio-card",
                    ),
                    html.Div(
                        [
                            html.Div("Effectifs", className="kpi-label"),
                            html.Div(total_staff, className="ratio-value"),
                        ],
                        className="ratio-card",
                    ),
                ],
                className="ratio-grid",
            ),
            html.Div(
                "Les marqueurs projettent le volume visible sur des p?les de r?f?rence faute de g?olocalisation agence par agence.",
                className="ratio-desc",
            ),
            html.Div(legend_items, className="bilan-legend"),
        ]
    )


# --- Table payloads ---------------------------------------------------------


def _build_raw_data_table_data(filtered: pd.DataFrame) -> list[dict[str, object]]:
    if filtered.empty:
        return []

    raw_columns = [
        "year",
        "company",
        "groupe_bancaire",
        "bilan",
        "produit_net_bancaire",
        "resultat_net",
        "roa",
        "roe",
    ]
    raw_frame = filtered.copy()
    for column in raw_columns:
        if column not in raw_frame.columns:
            raw_frame[column] = pd.NA
    raw_frame = raw_frame[raw_columns].sort_values(["year", "company"], ascending=[False, True], kind="stable")
    return raw_frame.to_dict("records")


# --- PDF export -------------------------------------------------------------


def _write_pdf_report(
    buffer: BytesIO,
    filtered: pd.DataFrame,
    snapshot_banks: pd.DataFrame,
    selected_year: object,
    selected_group: object,
    selected_bank: object,
) -> None:
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    pdf.setFillColor(HexColor(BANKING_BACKGROUND))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    pdf.setFillColor(HexColor(BANKING_GOLD))
    pdf.setFont("Helvetica-Bold", 21)
    pdf.drawString(42, page_height - 58, "Tableau de Bord Analytique - Secteur Bancaire Senegalais")

    pdf.setFillColor(HexColor("#f6f0e6"))
    pdf.setFont("Helvetica", 11)
    pdf.drawString(42, page_height - 84, "Export PDF du dashboard bancaire Dash / Plotly")

    year_label = "Toutes les annees" if selected_year in (None, ALL_FILTER_VALUE) else str(selected_year)
    group_label = "Tous les groupes" if selected_group in (None, ALL_FILTER_VALUE) else str(selected_group)
    bank_label = "Toutes les banques" if selected_bank in (None, ALL_FILTER_VALUE) else str(selected_bank)
    pdf.drawString(42, page_height - 112, f"Filtres actifs  |  Annee: {year_label}  |  Groupe: {group_label}  |  Banque: {bank_label}")

    snapshot_frame = _select_latest_year_snapshot(filtered)
    kpis = [
        ("Total actif secteur", _format_kpi_metric(snapshot_frame, "bilan")),
        ("Produit Net Bancaire", _format_kpi_metric(snapshot_frame, "produit_net_bancaire")),
        ("Resultat net", _format_kpi_metric(snapshot_frame, "resultat_net")),
        ("Capitaux propres", _format_kpi_metric(snapshot_frame, "fonds_propres")),
        ("Nombre banques", f"{snapshot_banks['company'].nunique()} banques" if not snapshot_banks.empty else "0 banque"),
    ]

    y_cursor = page_height - 155
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(42, y_cursor, "KPI du snapshot")
    y_cursor -= 24
    pdf.setFont("Helvetica", 11)
    for label, value in kpis:
        pdf.drawString(54, y_cursor, f"- {label}: {value}")
        y_cursor -= 18

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(42, y_cursor - 8, "Top banques du snapshot")
    y_cursor -= 32
    pdf.setFont("Helvetica", 10)

    ranking_frame = snapshot_banks[["company", "groupe_bancaire", "bilan", "produit_net_bancaire", "resultat_net"]].head(10)
    for _, row in ranking_frame.iterrows():
        line = (
            f"{row['company']} | {row['groupe_bancaire']} | Actif: {format_number(row['bilan'], suffix=' FCFA')} | "
            f"PNB: {format_number(row['produit_net_bancaire'], suffix=' FCFA')} | "
            f"RN: {format_number(row['resultat_net'], suffix=' FCFA')}"
        )
        pdf.drawString(54, y_cursor, line[:115])
        y_cursor -= 16
        if y_cursor < 72:
            pdf.showPage()
            pdf.setFillColor(HexColor(BANKING_BACKGROUND))
            pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
            pdf.setFillColor(HexColor("#f6f0e6"))
            pdf.setFont("Helvetica", 10)
            y_cursor = page_height - 56

    pdf.save()

# --- Callback registration --------------------------------------------------


def register_banking_callbacks(app: Dash, dataframe_provider: Callable[[], pd.DataFrame]) -> None:
    def _get_prepared_dataframe() -> pd.DataFrame:
        return _prepare_banking_dataframe(dataframe_provider())


    @app.callback(
        Output("banking-compare-bank-selector", "options"),
        Output("banking-compare-bank-selector", "value"),
        Output("banking-compare-helper", "children"),
        Input("banking-year-filter", "value"),
        Input("banking-group-filter", "value"),
        Input("banking-bank-filter", "value"),
        State("banking-compare-bank-selector", "value"),
    )
    def update_compare_selector(
        selected_year: object,
        selected_group: object,
        selected_bank: object,
        selected_compare_banks: list[str] | None,
    ) -> tuple[list[dict[str, object]], list[str], str]:
        prepared_dataframe = _get_prepared_dataframe()
        filtered = _filter_banking_dataframe(prepared_dataframe, selected_year, selected_group, selected_bank)
        snapshot_banks = _aggregate_snapshot_by_company(_select_latest_year_snapshot(filtered))
        options = [
            {"label": bank, "value": bank}
            for bank in snapshot_banks.get("company", pd.Series(dtype="object")).dropna().astype(str).tolist()
        ]
        selected_values = _normalize_compare_selection(snapshot_banks, selected_compare_banks, selected_bank)
        helper = f"{len(selected_values)} banque(s) selectionnee(s) - maximum 6."
        return options, selected_values, helper

    @app.callback(
        Output("banking-kpi-sector-assets", "children"),
        Output("banking-kpi-sector-pnb", "children"),
        Output("banking-kpi-sector-net-result", "children"),
        Output("banking-kpi-sector-equity", "children"),
        Output("banking-kpi-sector-bank-count", "children"),
        Output("banking-kpi-sector-roa", "children"),
        Output("banking-kpi-sector-roe", "children"),
        Output("banking-kpi-sector-assets-trend", "children"),
        Output("banking-kpi-sector-assets-trend", "className"),
        Output("banking-kpi-sector-pnb-trend", "children"),
        Output("banking-kpi-sector-pnb-trend", "className"),
        Output("banking-kpi-sector-net-result-trend", "children"),
        Output("banking-kpi-sector-net-result-trend", "className"),
        Output("banking-ratio-roa", "children"),
        Output("banking-ratio-roe", "children"),
        Output("banking-ratio-nim", "children"),
        Output("banking-ratio-cir", "children"),
        Output("banking-ratio-er", "children"),
        Output("banking-ratio-roa-bar", "style"),
        Output("banking-ratio-roe-bar", "style"),
        Output("banking-ratio-nim-bar", "style"),
        Output("banking-ratio-cir-bar", "style"),
        Output("banking-ratio-er-bar", "style"),
        Output("banking-analysis-bank-meta", "children"),
        Output("banking-bilan-kpi-assets", "children"),
        Output("banking-bilan-kpi-emplois", "children"),
        Output("banking-bilan-kpi-ressources", "children"),
        Output("banking-bilan-kpi-equity", "children"),
        Output("banking-bilan-kpi-nim", "children"),
        Output("banking-bilan-kpi-cir", "children"),
        Output("banking-sector-assets-graph", "figure"),
        Output("banking-sector-pnb-graph", "figure"),
        Output("banking-sector-result-graph", "figure"),
        Output("banking-sector-ressources-emplois-graph", "figure"),
        Output("banking-sector-funds-graph", "figure"),
        Output("banking-sector-group-share-graph", "figure"),
        Output("banking-structure-assets-graph", "figure"),
        Output("banking-structure-liabilities-graph", "figure"),
        Output("banking-structure-client-graph", "figure"),
        Output("banking-structure-ratio-graph", "figure"),
        Output("banking-ratios-roa-roe-graph", "figure"),
        Output("banking-ratios-nim-cir-graph", "figure"),
        Output("banking-ratios-roa-bank-graph", "figure"),
        Output("banking-ratios-cir-bank-graph", "figure"),
        Output("banking-ranking-assets-graph", "figure"),
        Output("banking-ranking-pnb-graph", "figure"),
        Output("banking-ranking-table", "data"),
        Output("banking-compare-evolution-graph", "figure"),
        Output("banking-compare-radar-graph", "figure"),
        Output("banking-compare-direct-graph", "figure"),
        Output("banking-analysis-bank-title", "children"),
        Output("banking-analysis-kpi-assets", "children"),
        Output("banking-analysis-kpi-pnb", "children"),
        Output("banking-analysis-kpi-result", "children"),
        Output("banking-analysis-kpi-roe", "children"),
        Output("banking-analysis-assets-graph", "figure"),
        Output("banking-analysis-pnb-graph", "figure"),
        Output("banking-analysis-result-graph", "figure"),
        Output("banking-analysis-res-emp-graph", "figure"),
        Output("banking-analysis-cp-graph", "figure"),
        Output("banking-analysis-network-graph", "figure"),
        Output("banking-map-graph", "figure"),
        Output("banking-map-agencies-graph", "figure"),
        Output("banking-map-staff-graph", "figure"),
        Output("banking-map-agencies-trend-graph", "figure"),
        Output("banking-map-staff-trend-graph", "figure"),
        Output("banking-map-legend-content", "children"),
        Output("banking-data-count", "children"),
        Output("banking-raw-data-table", "data"),
        Input("banking-year-filter", "value"),
        Input("banking-group-filter", "value"),
        Input("banking-bank-filter", "value"),
        Input("banking-compare-bank-selector", "value"),
    )
    def update_banking_dashboard(
        selected_year: object,
        selected_group: object,
        selected_bank: object,
        selected_compare_banks: list[str] | None,
    ) -> tuple[object, ...]:
        prepared_dataframe = _get_prepared_dataframe()
        filtered = _filter_banking_dataframe(prepared_dataframe, selected_year, selected_group, selected_bank)
        snapshot_frame = _select_latest_year_snapshot(filtered)
        snapshot_banks = _aggregate_snapshot_by_company(snapshot_frame)
        group_snapshot = _aggregate_by_group(snapshot_frame)
        yearly = _aggregate_by_year(filtered)
        bank_year = _aggregate_by_bank_year(filtered)
        sector_ratio_snapshot = _build_sector_ratio_snapshot(snapshot_frame)
        raw_data_count = f"{len(filtered):,}".replace(",", " ") + f" lignes · {snapshot_banks['company'].nunique() if not snapshot_banks.empty else 0} banques"

        # Previous year frame for trend computation
        prev_year_frame: pd.DataFrame = pd.DataFrame()
        if not filtered.empty and "year" in filtered.columns:
            sorted_years = sorted(filtered["year"].dropna().unique())
            if len(sorted_years) >= 2:
                prev_year = sorted_years[-2]
                prev_year_frame = filtered[filtered["year"] == prev_year].copy()

        def _col_sum(frame: pd.DataFrame, col: str) -> float | None:
            if frame.empty or col not in frame.columns:
                return None
            val = frame[col].sum(min_count=1)
            return float(val) if not pd.isna(val) else None

        def _trend_pill(curr: float | None, prev: float | None) -> tuple[list, str]:
            if curr is None or prev is None or prev == 0:
                return [html.Strong("—"), html.Small("vs N-1")], "kpi-trend neutral"
            pct = (curr - prev) / abs(prev) * 100
            if pct >= 0:
                return [html.Strong(f"↑ {abs(pct):.1f}%"), html.Small("vs N-1")], "kpi-trend up"
            return [html.Strong(f"↓ {abs(pct):.1f}%"), html.Small("vs N-1")], "kpi-trend down"

        def _bar_style(ratio_val: object, max_pct: float, color: str) -> dict:
            if ratio_val is None or pd.isna(ratio_val):
                return {"width": "0%", "background": color}
            pct = min(abs(float(ratio_val) * 100) / max_pct * 100, 100)
            return {"width": f"{pct:.1f}%", "background": color}

        curr_assets = _col_sum(snapshot_frame, "bilan")
        prev_assets = _col_sum(prev_year_frame, "bilan")
        curr_pnb = _col_sum(snapshot_frame, "produit_net_bancaire")
        prev_pnb = _col_sum(prev_year_frame, "produit_net_bancaire")
        curr_rn = _col_sum(snapshot_frame, "resultat_net")
        prev_rn = _col_sum(prev_year_frame, "resultat_net")

        assets_trend_children, assets_trend_class = _trend_pill(curr_assets, prev_assets)
        pnb_trend_children, pnb_trend_class = _trend_pill(curr_pnb, prev_pnb)
        rn_trend_children, rn_trend_class = _trend_pill(curr_rn, prev_rn)

        roa_val = sector_ratio_snapshot.get("roa")
        roe_val = sector_ratio_snapshot.get("roe")
        nim_val = sector_ratio_snapshot.get("nim")
        cir_val = sector_ratio_snapshot.get("coefficient_exploitation")
        er_val = sector_ratio_snapshot.get("emplois_ressources_ratio")

        sector_roa_kpi = _format_ratio_value(roa_val)
        sector_roe_kpi = _format_ratio_value(roe_val)

        compare_banks = _normalize_compare_selection(snapshot_banks, selected_compare_banks, selected_bank)
        compare_snapshot = snapshot_banks[snapshot_banks["company"].isin(compare_banks)].copy() if not snapshot_banks.empty else snapshot_banks
        compare_history = bank_year[bank_year["company"].isin(compare_banks)].copy() if not bank_year.empty else bank_year

        focus_bank = _resolve_focus_bank(snapshot_banks, selected_bank)
        focus_snapshot = snapshot_banks[snapshot_banks["company"] == focus_bank].head(1) if focus_bank else pd.DataFrame()
        focus_history = bank_year[bank_year["company"] == focus_bank].copy() if focus_bank else pd.DataFrame()

        total_assets = _format_kpi_metric(snapshot_frame, "bilan")
        total_pnb = _format_kpi_metric(snapshot_frame, "produit_net_bancaire")
        total_result = _format_kpi_metric(snapshot_frame, "resultat_net")
        total_equity = _format_kpi_metric(snapshot_frame, "fonds_propres")
        bank_count = f"{snapshot_banks['company'].nunique()} banques" if not snapshot_banks.empty else "0 banque"

        if focus_snapshot.empty:
            analysis_title = "Analyse detaillee - aucune banque disponible"
            bank_meta = "Selectionnez une banque pour voir son analyse detaillee."
            focus_assets = "N/A"
            focus_pnb = "N/A"
            focus_result = "N/A"
            focus_roe = "N/A"
        else:
            row = focus_snapshot.iloc[0]
            analysis_title = f"{row['company']}"
            groupe_label = row.get("groupe_bancaire") or "Groupe N/A"
            years_present = sorted(bank_year[bank_year["company"] == focus_bank]["year"].unique()) if focus_bank else []
            years_range = f"{years_present[0]}\u2013{years_present[-1]}" if len(years_present) >= 2 else str(years_present[0]) if years_present else ""
            bank_meta = f"{groupe_label} · {years_range} · {len(years_present)} ann\u00e9es"
            focus_assets = format_number(row.get("bilan"), suffix=" FCFA")
            focus_pnb = format_number(row.get("produit_net_bancaire"), suffix=" FCFA")
            focus_result = format_number(row.get("resultat_net"), suffix=" FCFA")
            focus_roe = _format_ratio_value(row.get("roe"))

        return (
            total_assets,
            total_pnb,
            total_result,
            total_equity,
            bank_count,
            sector_roa_kpi,
            sector_roe_kpi,
            assets_trend_children,
            assets_trend_class,
            pnb_trend_children,
            pnb_trend_class,
            rn_trend_children,
            rn_trend_class,
            _format_ratio_value(roa_val),
            _format_ratio_value(roe_val),
            _format_ratio_value(nim_val),
            _format_ratio_value(cir_val, decimals=1),
            _format_ratio_value(er_val, decimals=2),
            _bar_style(roa_val, 5.0, "#2980b9"),
            _bar_style(roe_val, 30.0, "#27ae60"),
            _bar_style(nim_val, 8.0, "#d4a017"),
            _bar_style(cir_val, 100.0, "#e74c3c"),
            _bar_style(er_val, 150.0, "#2980b9"),
            bank_meta,
            _format_kpi_metric(snapshot_frame, "bilan"),
            _format_kpi_metric(snapshot_frame, "emploi"),
            _format_kpi_metric(snapshot_frame, "ressources"),
            _format_kpi_metric(snapshot_frame, "fonds_propres"),
            _format_ratio_value(nim_val),
            _format_ratio_value(cir_val, decimals=1),
            _build_metric_line_figure(yearly, "bilan", "Evolution total actif", "FCFA"),
            _build_metric_line_figure(yearly, "produit_net_bancaire", "Evolution PNB", "FCFA"),
            _build_metric_line_figure(yearly, "resultat_net", "Evolution resultat net", "FCFA"),
            _build_sector_resources_vs_emplois_figure(yearly),
            _build_metric_line_figure(yearly, "fonds_propres", "Capitaux propres", "FCFA"),
            _build_group_share_figure(group_snapshot),
            _build_asset_structure_figure(snapshot_frame),
            _build_liability_structure_figure(snapshot_frame),
            _build_client_balance_figure(snapshot_banks),
            _build_ratio_emplois_ressources_figure(snapshot_banks),
            _build_dual_ratio_line_figure(yearly, "roa", "roe", "Evolution ROA / ROE", "ROA", "ROE"),
            _build_dual_ratio_line_figure(
                yearly,
                "nim",
                "coefficient_exploitation",
                "Evolution NIM / CIR",
                "NIM",
                "CIR",
            ),
            _build_ratio_bank_figure(snapshot_banks, "roa", "ROA par banque"),
            _build_ratio_bank_figure(snapshot_banks, "coefficient_exploitation", "CIR par banque"),
            _build_top_banks_figure(snapshot_banks, "bilan", "Top banques - total actif"),
            _build_top_banks_figure(snapshot_banks, "produit_net_bancaire", "Top banques - PNB"),
            _build_ranking_table_data(snapshot_banks),
            _build_compare_evolution_figure(compare_history),
            _build_radar_figure(compare_snapshot),
            _build_direct_comparison_figure(compare_snapshot),
            analysis_title,
            focus_assets,
            focus_pnb,
            focus_result,
            focus_roe,
            _build_bank_history_figure(focus_history, "bilan", "Evolution bilan"),
            _build_bank_history_figure(focus_history, "produit_net_bancaire", "Evolution PNB"),
            _build_bank_history_figure(focus_history, "resultat_net", "Evolution resultat"),
            _build_bank_res_emp_figure(focus_history),
            _build_bank_cp_figure(focus_history),
            _build_bank_network_figure(focus_history),
            _build_presence_map(snapshot_banks),
            _build_agencies_bank_figure(snapshot_banks),
            _build_staff_bank_figure(snapshot_banks),
            _build_agencies_trend_figure(yearly),
            _build_staff_trend_figure(yearly),
            _build_map_legend_content(snapshot_banks),
            raw_data_count,
            _build_raw_data_table_data(filtered),
        )

    @app.callback(
        Output("banking-export-download", "data"),
        Input("banking-export-pdf-button", "n_clicks"),
        State("banking-year-filter", "value"),
        State("banking-group-filter", "value"),
        State("banking-bank-filter", "value"),
        prevent_initial_call=True,
    )
    def export_banking_pdf(
        n_clicks: int | None,
        selected_year: object,
        selected_group: object,
        selected_bank: object,
    ) -> object:
        if not n_clicks:
            raise PreventUpdate

        prepared_dataframe = _get_prepared_dataframe()
        filtered = _filter_banking_dataframe(prepared_dataframe, selected_year, selected_group, selected_bank)
        snapshot_banks = _aggregate_snapshot_by_company(_select_latest_year_snapshot(filtered))

        def _writer(buffer: BytesIO) -> None:
            _write_pdf_report(buffer, filtered, snapshot_banks, selected_year, selected_group, selected_bank)

        return dcc.send_bytes(_writer, "dashboard_bancaire_senegal.pdf")

    @app.callback(
        Output("banking-year-filter", "value"),
        Output("banking-group-filter", "value"),
        Output("banking-bank-filter", "value"),
        Input("banking-reset-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_banking_filters(n_clicks: int | None) -> tuple[str, str, str]:
        return ALL_FILTER_VALUE, ALL_FILTER_VALUE, ALL_FILTER_VALUE


def create_banking_dashboard(
    server: Flask,
    callback_dataframe_provider: Callable[[], pd.DataFrame],
    error_provider: Callable[[], str | None] | None = None,
    layout_dataframe_provider: Callable[[], pd.DataFrame] | None = None,
) -> Dash:
    """Create the independent Dash app mounted on /banking/."""

    dash_app = Dash(
        name="banking_dashboard",
        server=server,
        url_base_pathname="/banking/",
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=False,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
        title="Dashboard Bancaire",
    )
    layout_dataframe_provider = layout_dataframe_provider or callback_dataframe_provider
    dash_app.layout = lambda: create_banking_layout(
        layout_dataframe_provider(),
        error_provider() if error_provider is not None else None,
    )
    register_banking_callbacks(dash_app, callback_dataframe_provider)
    return dash_app


