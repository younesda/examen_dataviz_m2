"""MongoDB connection utilities for the data visualization project."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

LOGGER = logging.getLogger(__name__)


def get_mongo_client(
    mongo_uri: str,
    app_name: str = "ExamDataviz",
    server_selection_timeout_ms: int = 10_000,
) -> MongoClient:
    """Create and validate a MongoDB client.

    Purpose:
        Open a MongoDB connection and validate it immediately with a ping so
        pipeline failures surface early and explicitly.

    Inputs:
        mongo_uri: Full MongoDB connection string.
        app_name: Name attached to the MongoDB client for observability.
        server_selection_timeout_ms: Timeout used by the MongoDB driver.

    Outputs:
        A connected and validated ``MongoClient`` instance.
    """

    if not mongo_uri:
        raise ValueError("A MongoDB URI is required to open a database connection.")

    LOGGER.info("Opening MongoDB connection.")

    try:
        client = MongoClient(
            mongo_uri,
            appname=app_name,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )
        client.admin.command("ping")
        LOGGER.info("MongoDB connection established successfully.")
        return client
    except PyMongoError as exc:
        raise ConnectionError("Unable to connect to MongoDB.") from exc


def get_database(client: MongoClient, database_name: str = "bank_dataviz") -> Database:
    """Return the target MongoDB database.

    Purpose:
        Centralise access to the application database name used by the
        ingestion pipeline.

    Inputs:
        client: An active ``MongoClient`` instance.
        database_name: Target MongoDB database name.

    Outputs:
        A ``Database`` object ready to use.
    """

    if client is None:
        raise ValueError("A valid MongoClient instance is required.")

    LOGGER.info("Using MongoDB database '%s'.", database_name)
    return client[database_name]


def dataframe_to_documents(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a pandas DataFrame into MongoDB-ready documents.

    Purpose:
        Replace pandas-specific missing values and timestamp objects with plain
        Python values accepted by ``pymongo``.

    Inputs:
        dataframe: DataFrame containing the records to insert.

    Outputs:
        A list of dictionaries suitable for MongoDB insertion.
    """

    documents: list[dict[str, Any]] = []

    for raw_record in dataframe.to_dict(orient="records"):
        cleaned_record: dict[str, Any] = {}

        for key, value in raw_record.items():
            if isinstance(value, pd.Timestamp):
                cleaned_record[key] = value.to_pydatetime()
            elif pd.isna(value):
                cleaned_record[key] = None
            elif hasattr(value, "item"):
                cleaned_record[key] = value.item()
            else:
                cleaned_record[key] = value

        documents.append(cleaned_record)

    return documents


def replace_collection_data(
    database: Database,
    collection_name: str,
    dataframe: pd.DataFrame,
) -> int:
    """Replace an entire MongoDB collection with a DataFrame payload.

    Purpose:
        Keep the ingestion script idempotent. Re-running the pipeline replaces
        the previous contents of a collection instead of creating duplicates.

    Inputs:
        database: Target MongoDB database.
        collection_name: Name of the collection to refresh.
        dataframe: Prepared DataFrame to insert.

    Outputs:
        The number of inserted documents.
    """

    if dataframe is None:
        raise ValueError("A DataFrame is required for MongoDB insertion.")

    collection: Collection = database[collection_name]
    documents = dataframe_to_documents(dataframe)

    LOGGER.info(
        "Refreshing collection '%s' with %s documents.",
        collection_name,
        len(documents),
    )

    try:
        collection.delete_many({})
        if documents:
            collection.insert_many(documents, ordered=False)
        return len(documents)
    except PyMongoError as exc:
        raise RuntimeError(
            f"Unable to refresh MongoDB collection '{collection_name}'."
        ) from exc
