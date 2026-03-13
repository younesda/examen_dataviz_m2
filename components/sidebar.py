"""Sidebar component for navigating between the three dashboards."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


NAVIGATION_ITEMS = [
    {"label": "📊 Banking", "href": "/banking"},
    {"label": "☀ Solar Energy", "href": "/solar"},
    {"label": "🛡 Insurance", "href": "/insurance"},
]


def build_sidebar() -> html.Div:
    """Build the main dashboard sidebar.

    Purpose:
        Provide a reusable and responsive navigation menu shared by all
        dashboard pages in the application.

    Inputs:
        None.

    Outputs:
        A Dash ``html.Div`` containing the sidebar markup.
    """

    nav_links = [
        dbc.NavLink(
            item["label"],
            href=item["href"],
            active="exact",
            className="sidebar-link",
        )
        for item in NAVIGATION_ITEMS
    ]

    return html.Div(
        [
            html.Div(
                [
                    html.Span("DataViz", className="sidebar-eyebrow"),
                    html.H2("Control Center", className="sidebar-title"),
                    html.P(
                        "Architecture Flask + Dash prete pour les dashboards metier.",
                        className="sidebar-description",
                    ),
                ],
                className="sidebar-brand",
            ),
            dbc.Nav(nav_links, vertical=True, pills=True, className="sidebar-nav"),
            html.Div(
                [
                    html.Span("Phase 2", className="sidebar-footer-label"),
                    html.P(
                        "Navigation, chargement MongoDB et structure des callbacks.",
                        className="sidebar-footer-text",
                    ),
                ],
                className="sidebar-footer",
            ),
        ],
        className="app-sidebar",
    )
