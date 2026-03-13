"""Insurance dataset preprocessing utilities."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


def normalize_column_name(column_name: str) -> str:
    """Normalize a raw column name to snake_case.

    Purpose:
        Keep the insurance schema clean and consistent before analytical
        enrichment and MongoDB insertion.

    Inputs:
        column_name: Source column name.

    Outputs:
        The normalized snake_case name.
    """

    normalized = (
        str(column_name)
        .strip()
        .lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(".", " ")
    )
    normalized = "_".join(part for part in normalized.split() if part)
    return normalized


def preprocess_insurance_data(data_directory: Path) -> pd.DataFrame:
    """Run the insurance dataset preprocessing pipeline.

    Purpose:
        Clean duplicates, normalize the schema, convert analytical fields and
        compute the requested profitability indicators.

    Inputs:
        data_directory: Directory containing ``insurance_dataset.csv``.

    Outputs:
        A cleaned and enriched insurance DataFrame.
    """

    csv_path = data_directory / "insurance_dataset.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing insurance dataset: {csv_path}")

    LOGGER.info("Loading insurance dataset from '%s'.", csv_path)
    dataframe = pd.read_csv(csv_path, sep=None, engine="python")
    dataframe.columns = [normalize_column_name(column) for column in dataframe.columns]

    initial_row_count = len(dataframe)
    dataframe = dataframe.drop_duplicates().copy()
    removed_duplicates = initial_row_count - len(dataframe)
    LOGGER.info("Removed %s duplicate insurance rows.", removed_duplicates)

    numeric_columns = [
        "age",
        "duree_contrat",
        "montant_prime",
        "nb_sinistres",
        "montant_sinistres",
        "bonus_malus",
    ]
    for column in numeric_columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")

    if "date_derniere_sinistre" in dataframe.columns:
        dataframe["date_derniere_sinistre"] = pd.to_datetime(
            dataframe["date_derniere_sinistre"],
            errors="coerce",
        )

    for column in ["sexe", "type_assurance", "region"]:
        if column in dataframe.columns:
            dataframe[column] = dataframe[column].astype(str).str.strip().str.lower()

    dataframe = dataframe.dropna(subset=["montant_prime", "montant_sinistres"]).copy()

    dataframe["premiums"] = dataframe["montant_prime"]
    dataframe["claims"] = dataframe["montant_sinistres"]
    dataframe["profit"] = dataframe["premiums"] - dataframe["claims"]
    dataframe["loss_ratio"] = dataframe["claims"].divide(
        dataframe["premiums"].replace({0: pd.NA})
    )
    dataframe["profit_margin"] = dataframe["profit"].divide(
        dataframe["premiums"].replace({0: pd.NA})
    )

    LOGGER.info("Insurance preprocessing completed with %s rows.", len(dataframe))
    return dataframe.reset_index(drop=True)
