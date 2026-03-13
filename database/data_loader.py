"""MongoDB-backed data loaders for the dashboard application."""

from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd

from database.mongo_connection import get_database

LOGGER = logging.getLogger(__name__)


def _convert_datetime_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convert date-like columns into pandas datetime values.

    Purpose:
        Ensure dashboard filtering and time-based visuals use consistent pandas
        datetime types regardless of how MongoDB returned the values.

    Inputs:
        dataframe: Raw DataFrame built from MongoDB documents.

    Outputs:
        The same DataFrame with date-like columns converted where possible.
    """

    for column in dataframe.columns:
        if "date" in column.lower():
            dataframe[column] = pd.to_datetime(dataframe[column], errors="coerce")
    return dataframe


def _ensure_year_column(
    dataframe: pd.DataFrame,
    candidate_columns: Iterable[str],
) -> pd.DataFrame:
    """Guarantee a shared ``year`` column for dashboard filters.

    Purpose:
        Normalize the year dimension across datasets that may expose it under
        different names or derive it from a datetime column.

    Inputs:
        dataframe: Input DataFrame.
        candidate_columns: Columns that may contain a year dimension.

    Outputs:
        The same DataFrame with a normalized ``year`` column.
    """

    if "year" in dataframe.columns:
        dataframe["year"] = pd.to_numeric(dataframe["year"], errors="coerce").astype("Int64")
        return dataframe

    for column in candidate_columns:
        if column not in dataframe.columns:
            continue

        series = dataframe[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            dataframe["year"] = series.dt.year.astype("Int64")
            return dataframe

        numeric_year = pd.to_numeric(series, errors="coerce")
        if numeric_year.notna().any():
            dataframe["year"] = numeric_year.astype("Int64")
            return dataframe

    dataframe["year"] = pd.Series([pd.NA] * len(dataframe), dtype="Int64")
    return dataframe


def _ensure_company_column(
    dataframe: pd.DataFrame,
    candidate_columns: Iterable[str],
    fallback_label: str,
) -> pd.DataFrame:
    """Guarantee a shared ``company`` column for dashboard filters.

    Purpose:
        Some collections do not expose a literal ``company`` field. This helper
        maps the closest business identifier to ``company`` so every dashboard
        can share the same filter contract.

    Inputs:
        dataframe: Input DataFrame.
        candidate_columns: Columns to inspect in priority order.
        fallback_label: Label used when no company-like column exists.

    Outputs:
        The same DataFrame with a normalized ``company`` column.
    """

    for column in candidate_columns:
        if column not in dataframe.columns:
            continue

        series = dataframe[column]
        if series.notna().any():
            dataframe["company"] = series.fillna(fallback_label).astype(str).str.strip()
            return dataframe

    dataframe["company"] = fallback_label
    return dataframe


def _finalize_dataframe(
    dataframe: pd.DataFrame,
    collection_name: str,
    company_candidates: Iterable[str],
    year_candidates: Iterable[str],
    fallback_company: str,
) -> pd.DataFrame:
    """Apply shared cleaning rules to a MongoDB-backed DataFrame.

    Purpose:
        Centralize type conversion, helper dimensions and sorting so every
        loader returns a clean and dashboard-ready DataFrame.

    Inputs:
        dataframe: Raw DataFrame from MongoDB.
        collection_name: Name of the source collection for logging.
        company_candidates: Potential company-identifying columns.
        year_candidates: Potential year columns or date columns.
        fallback_company: Default company label when no source column exists.

    Outputs:
        A clean DataFrame ready for dashboard consumption.
    """

    if dataframe.empty:
        LOGGER.warning("Collection '%s' returned no documents.", collection_name)
        return pd.DataFrame(columns=["company", "year"])

    dataframe = dataframe.convert_dtypes()
    dataframe = _convert_datetime_columns(dataframe)
    dataframe = _ensure_year_column(dataframe, year_candidates)
    dataframe = _ensure_company_column(dataframe, company_candidates, fallback_company)
    dataframe = dataframe.sort_values(
        by=[column for column in ["year", "company"] if column in dataframe.columns],
        kind="stable",
    ).reset_index(drop=True)

    LOGGER.info("Loaded %s rows from '%s'.", len(dataframe), collection_name)
    return dataframe


def _load_collection(
    collection_name: str,
    company_candidates: Iterable[str],
    year_candidates: Iterable[str],
    fallback_company: str,
) -> pd.DataFrame:
    """Load a MongoDB collection into a pandas DataFrame.

    Purpose:
        Encapsulate the collection-to-DataFrame conversion shared by the three
        domain-specific loaders.

    Inputs:
        collection_name: MongoDB collection name.
        company_candidates: Candidate columns for the shared company filter.
        year_candidates: Candidate columns for the shared year filter.
        fallback_company: Default company label when no company column exists.

    Outputs:
        A cleaned pandas DataFrame.
    """

    database = get_database()
    records = list(database[collection_name].find({}, {"_id": 0}))
    dataframe = pd.DataFrame(records)
    return _finalize_dataframe(
        dataframe=dataframe,
        collection_name=collection_name,
        company_candidates=company_candidates,
        year_candidates=year_candidates,
        fallback_company=fallback_company,
    )


def load_banking_data() -> pd.DataFrame:
    """Load banking data from MongoDB.

    Purpose:
        Retrieve the banking dataset, normalize its shared dimensions and return
        a pandas DataFrame ready for dashboard filtering.

    Inputs:
        None.

    Outputs:
        A cleaned banking DataFrame.
    """

    return _load_collection(
        collection_name="banking_data",
        company_candidates=["company", "bank_name", "bank", "sigle"],
        year_candidates=["year", "annee"],
        fallback_company="Banking Portfolio",
    )


def load_solar_data() -> pd.DataFrame:
    """Load solar energy data from MongoDB.

    Purpose:
        Retrieve the solar dataset, derive shared filter columns and return a
        clean DataFrame for the dashboard layer.

    Inputs:
        None.

    Outputs:
        A cleaned solar DataFrame.
    """

    return _load_collection(
        collection_name="solar_energy_data",
        company_candidates=["company", "plant_name", "site_name"],
        year_candidates=["year", "date"],
        fallback_company="Solar Portfolio",
    )


def load_insurance_data() -> pd.DataFrame:
    """Load insurance data from MongoDB.

    Purpose:
        Retrieve the insurance dataset and normalize a shared company filter.
        When no insurer name exists, ``type_assurance`` is used as the most
        meaningful business grouping for the application shell.

    Inputs:
        None.

    Outputs:
        A cleaned insurance DataFrame.
    """

    return _load_collection(
        collection_name="insurance_data",
        company_candidates=["company", "insurer", "type_assurance"],
        year_candidates=["year", "date_derniere_sinistre"],
        fallback_company="Insurance Portfolio",
    )
