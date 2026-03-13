"""MongoDB connection helpers for the Flask + Dash application."""

from __future__ import annotations

import logging
import os

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

LOGGER = logging.getLogger(__name__)

DEFAULT_MONGO_URI = (
    "mongodb+srv://younes_dataviz:Mongo2026@examdataviz.h1v5vwa.mongodb.net/"
    "?appName=ExamDataviz"
)
DEFAULT_DATABASE_NAME = "bank_dataviz"
_CACHED_CLIENT: MongoClient | None = None
_CACHED_ERROR: Exception | None = None


def resolve_mongo_uri(mongo_uri: str | None = None) -> str:
    """Resolve the MongoDB URI used by the web application.

    Purpose:
        Centralize URI resolution so the application can use an explicit
        argument, then an environment variable, and finally the project default.

    Inputs:
        mongo_uri: Optional URI passed directly by the caller.

    Outputs:
        The MongoDB connection string that should be used.
    """

    resolved_uri = mongo_uri or os.getenv("MONGO_URI") or DEFAULT_MONGO_URI
    if not resolved_uri:
        raise ValueError("A MongoDB URI is required to connect to MongoDB.")
    return resolved_uri


def get_mongo_client(
    mongo_uri: str | None = None,
    app_name: str = "BankDataVizWebApp",
    server_selection_timeout_ms: int = 6_000,
) -> MongoClient:
    """Create and validate a cached MongoDB client.

    Purpose:
        Reuse a live MongoDB client across callbacks and page loads while still
        validating the connection early with a ping command. When a connection
        attempt fails, the error is cached so the app can degrade quickly.

    Inputs:
        mongo_uri: Optional MongoDB connection string override.
        app_name: Application name sent to MongoDB for observability.
        server_selection_timeout_ms: Timeout used during server selection.

    Outputs:
        A validated ``MongoClient`` instance.
    """

    global _CACHED_CLIENT, _CACHED_ERROR

    if _CACHED_CLIENT is not None:
        return _CACHED_CLIENT

    if _CACHED_ERROR is not None:
        raise ConnectionError("Unable to connect to MongoDB for the web application.") from _CACHED_ERROR

    resolved_uri = resolve_mongo_uri(mongo_uri)
    LOGGER.info("Opening MongoDB connection for the Dash web application.")

    try:
        client = MongoClient(
            resolved_uri,
            appname=app_name,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )
        client.admin.command("ping")
        LOGGER.info("MongoDB connection validated successfully.")
        _CACHED_CLIENT = client
        return client
    except PyMongoError as exc:
        _CACHED_ERROR = exc
        raise ConnectionError("Unable to connect to MongoDB for the web application.") from exc


def get_database(
    database_name: str = DEFAULT_DATABASE_NAME,
    mongo_uri: str | None = None,
) -> Database:
    """Return the application database instance.

    Purpose:
        Expose a single helper that returns the target MongoDB database used by
        the dashboards.

    Inputs:
        database_name: Name of the database to use.
        mongo_uri: Optional MongoDB connection string override.

    Outputs:
        A ``Database`` object bound to the requested MongoDB database.
    """

    client = get_mongo_client(mongo_uri=mongo_uri)
    LOGGER.info("Using MongoDB database '%s'.", database_name)
    return client[database_name]
