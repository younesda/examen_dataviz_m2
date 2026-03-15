"""MongoDB connection helpers for the Flask + Dash application."""

from __future__ import annotations

import logging
import os
import threading

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

LOGGER = logging.getLogger(__name__)

DEFAULT_MONGO_URI = (
    "mongodb://younes_dataviz:Mongo2026@"
    "ac-fbnhmqd-shard-00-00.h1v5vwa.mongodb.net:27017,"
    "ac-fbnhmqd-shard-00-01.h1v5vwa.mongodb.net:27017,"
    "ac-fbnhmqd-shard-00-02.h1v5vwa.mongodb.net:27017/"
    "?authSource=admin&replicaSet=atlas-5tfh8u-shard-0&tls=true"
    "&retryWrites=true&w=majority&appName=ExamDataviz"
)
DEFAULT_DATABASE_NAME = "bank_dataviz"
_CACHED_CLIENT: MongoClient | None = None
_CACHED_URI: str | None = None
_CACHE_LOCK = threading.Lock()


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


def _is_client_available(client: MongoClient) -> bool:
    """Return whether the cached client still responds to a lightweight ping."""

    try:
        client.admin.command("ping")
    except PyMongoError:
        return False
    return True


def _close_client(client: MongoClient) -> None:
    """Best-effort client close helper used when rotating the cache."""

    try:
        client.close()
    except PyMongoError:
        LOGGER.debug("MongoDB client close failed during cache rotation.", exc_info=True)


def reset_mongo_client() -> None:
    """Close and clear the cached MongoDB client.

    Purpose:
        Force the next read path to create a fresh client after a network hiccup
        or a failed server selection.

    Inputs:
        None.

    Outputs:
        None.
    """

    global _CACHED_CLIENT, _CACHED_URI

    with _CACHE_LOCK:
        if _CACHED_CLIENT is not None:
            _close_client(_CACHED_CLIENT)
        _CACHED_CLIENT = None
        _CACHED_URI = None


def get_mongo_client(
    mongo_uri: str | None = None,
    app_name: str = "BankDataVizWebApp",
    server_selection_timeout_ms: int = 1_500,
    *,
    force_refresh: bool = False,
) -> MongoClient:
    """Create and validate a cached MongoDB client.

    Purpose:
        Reuse a live MongoDB client across callbacks and page loads while still
        validating the connection early with a ping command. If the cached
        client becomes unavailable, it is discarded and recreated.

    Inputs:
        mongo_uri: Optional MongoDB connection string override.
        app_name: Application name sent to MongoDB for observability.
        server_selection_timeout_ms: Timeout used during server selection.
        force_refresh: When ``True``, always discard the cached client and open
            a fresh one.

    Outputs:
        A validated ``MongoClient`` instance.
    """

    global _CACHED_CLIENT, _CACHED_URI

    resolved_uri = resolve_mongo_uri(mongo_uri)

    with _CACHE_LOCK:
        if _CACHED_CLIENT is not None and _CACHED_URI != resolved_uri:
            _close_client(_CACHED_CLIENT)
            _CACHED_CLIENT = None
            _CACHED_URI = None

        if force_refresh and _CACHED_CLIENT is not None:
            _close_client(_CACHED_CLIENT)
            _CACHED_CLIENT = None
            _CACHED_URI = None

        if _CACHED_CLIENT is not None:
            if _is_client_available(_CACHED_CLIENT):
                return _CACHED_CLIENT

            LOGGER.warning("Cached MongoDB client is no longer healthy. Reconnecting.")
            _close_client(_CACHED_CLIENT)
            _CACHED_CLIENT = None
            _CACHED_URI = None

        LOGGER.info("Opening MongoDB connection for the Dash web application.")
        client = MongoClient(
            resolved_uri,
            appname=app_name,
            retryReads=True,
            retryWrites=True,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
            connectTimeoutMS=server_selection_timeout_ms,
            socketTimeoutMS=max(server_selection_timeout_ms * 3, 15_000),
        )

        try:
            client.admin.command("ping")
            LOGGER.info("MongoDB connection validated successfully.")
        except PyMongoError as exc:
            _close_client(client)
            raise ConnectionError("Unable to connect to MongoDB for the web application.") from exc

        _CACHED_CLIENT = client
        _CACHED_URI = resolved_uri
        return client


def get_database(
    database_name: str = DEFAULT_DATABASE_NAME,
    mongo_uri: str | None = None,
    *,
    force_refresh: bool = False,
) -> Database:
    """Return the application database instance.

    Purpose:
        Expose a single helper that returns the target MongoDB database used by
        the dashboards.

    Inputs:
        database_name: Name of the database to use.
        mongo_uri: Optional MongoDB connection string override.
        force_refresh: When ``True``, reopen the MongoDB client before reading.

    Outputs:
        A ``Database`` object bound to the requested MongoDB database.
    """

    client = get_mongo_client(mongo_uri=mongo_uri, force_refresh=force_refresh)
    LOGGER.info("Using MongoDB database '%s'.", database_name)
    return client[database_name]
