"""Flask + Dash application entry point for the data visualization platform."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, dcc, html
from flask import Flask

from components.sidebar import build_sidebar
from dashboards.banking_dashboard import register_banking_callbacks
from dashboards.insurance_dashboard import register_insurance_callbacks
from dashboards.solar_dashboard import register_solar_callbacks
from database.data_loader import load_banking_data, load_insurance_data, load_solar_data
from layouts.banking_layout import create_banking_layout
from layouts.insurance_layout import create_insurance_layout
from layouts.solar_layout import create_solar_layout

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DatasetState:
    """Runtime state associated with one MongoDB-backed dataset.

    Purpose:
        Keep the application shell explicit by storing both the DataFrame and
        the load status used by the global layout.

    Inputs:
        name: Dataset identifier used inside the app.
        dataframe: Loaded pandas DataFrame.
        error_message: Optional loading error captured during startup.

    Outputs:
        A small immutable-like container used by the app factory.
    """

    name: str
    dataframe: pd.DataFrame
    error_message: str | None = None


def configure_logging() -> None:
    """Configure application logging.

    Purpose:
        Provide consistent logs for startup, MongoDB loading and app lifecycle
        events.

    Inputs:
        None.

    Outputs:
        None. The Python logging system is configured in-place.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


configure_logging()


def _load_dataset(name: str, loader: Callable[[], pd.DataFrame]) -> DatasetState:
    """Load one dataset while capturing application-friendly errors.

    Purpose:
        Allow the Dash shell to start even if one collection is temporarily
        unreachable, while still surfacing the issue to the user.

    Inputs:
        name: Human-readable dataset identifier.
        loader: Data loader function that returns a pandas DataFrame.

    Outputs:
        A ``DatasetState`` containing the DataFrame and any startup error.
    """

    try:
        dataframe = loader()
        return DatasetState(name=name, dataframe=dataframe)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Unable to load the %s dataset from MongoDB: %s", name, exc)
        return DatasetState(name=name, dataframe=pd.DataFrame(), error_message=str(exc))



def load_application_data() -> dict[str, DatasetState]:
    """Load the three dashboard datasets from MongoDB.

    Purpose:
        Build a central data registry used by the Flask + Dash application.

    Inputs:
        None.

    Outputs:
        A dictionary keyed by dashboard name with one ``DatasetState`` per page.
    """

    return {
        "banking": _load_dataset("banking", load_banking_data),
        "solar": _load_dataset("solar", load_solar_data),
        "insurance": _load_dataset("insurance", load_insurance_data),
    }


APPLICATION_DATA = load_application_data()


def create_flask_server() -> Flask:
    """Create the hosting Flask server.

    Purpose:
        Provide the underlying WSGI server used to host the embedded Dash app.

    Inputs:
        None.

    Outputs:
        A configured ``Flask`` application instance.
    """

    return Flask(__name__)



def build_status_banner(dataset_states: dict[str, DatasetState]) -> dbc.Alert:
    """Build a startup status banner for the application shell.

    Purpose:
        Give immediate feedback about MongoDB connectivity and dataset loading
        when the application opens.

    Inputs:
        dataset_states: Loaded dataset registry.

    Outputs:
        A ``dbc.Alert`` summarizing the loading state.
    """

    errors = [state for state in dataset_states.values() if state.error_message]
    if errors:
        message = " | ".join(
            f"{state.name}: {state.error_message}" for state in errors
        )
        return dbc.Alert(
            f"MongoDB warning: {message}",
            color="danger",
            className="status-banner",
        )

    summary = " | ".join(
        f"{state.name}: {len(state.dataframe)} rows" for state in dataset_states.values()
    )
    return dbc.Alert(
        f"MongoDB connected successfully. {summary}",
        color="info",
        className="status-banner",
    )



def build_not_found_layout() -> html.Div:
    """Create a simple 404 layout.

    Purpose:
        Handle unknown routes without breaking the global application shell.

    Inputs:
        None.

    Outputs:
        A Dash layout fragment for unknown pages.
    """

    return html.Div(
        [
            html.Span("Page not found", className="page-eyebrow"),
            html.H1("Unknown dashboard", className="page-title"),
            html.P(
                "Use the sidebar to open Banking, Solar Energy or Insurance.",
                className="page-subtitle",
            ),
        ],
        className="dashboard-page",
    )



def create_dash_app(
    flask_server: Flask,
    dataset_states: dict[str, DatasetState],
) -> Dash:
    """Create the Dash application hosted inside Flask.

    Purpose:
        Configure the Dash shell, register routing and attach page callbacks.

    Inputs:
        flask_server: Flask server that hosts the Dash application.
        dataset_states: Dataset registry loaded from MongoDB.

    Outputs:
        A configured ``Dash`` application instance.
    """

    dash_app = Dash(
        __name__,
        server=flask_server,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
        title="Bank DataViz",
    )

    def serve_layout() -> html.Div:
        return html.Div(
            [
                dcc.Location(id="url"),
                html.Div(
                    [
                        build_sidebar(),
                        html.Div(
                            [
                                build_status_banner(dataset_states),
                                html.Div(id="dashboard-container", className="dashboard-container"),
                            ],
                            className="dashboard-content-shell",
                        ),
                    ],
                    className="app-shell",
                ),
            ],
            className="app-root",
        )

    dash_app.layout = serve_layout

    @dash_app.callback(Output("dashboard-container", "children"), Input("url", "pathname"))
    def render_page(pathname: str | None) -> html.Div:
        normalized_path = (pathname or "/banking").lower()
        if normalized_path in {"/", "/banking"}:
            return create_banking_layout(
                dataframe=dataset_states["banking"].dataframe,
                error_message=dataset_states["banking"].error_message,
            )
        if normalized_path == "/solar":
            return create_solar_layout(
                dataframe=dataset_states["solar"].dataframe,
                error_message=dataset_states["solar"].error_message,
            )
        if normalized_path == "/insurance":
            return create_insurance_layout(
                dataframe=dataset_states["insurance"].dataframe,
                error_message=dataset_states["insurance"].error_message,
            )
        return build_not_found_layout()

    register_banking_callbacks(dash_app, dataset_states["banking"].dataframe)
    register_solar_callbacks(dash_app, dataset_states["solar"].dataframe)
    register_insurance_callbacks(dash_app, dataset_states["insurance"].dataframe)

    return dash_app


flask_server = create_flask_server()
dash_app = create_dash_app(flask_server, APPLICATION_DATA)
server = flask_server


if __name__ == "__main__":
    LOGGER.info("Starting Flask + Dash application.")
    dash_app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8050")),
        debug=os.getenv("DASH_DEBUG", "false").lower() == "true",
    )
