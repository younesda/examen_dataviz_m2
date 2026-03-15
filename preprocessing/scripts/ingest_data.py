"""Main ingestion script for the Dash + Flask + MongoDB project."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from preprocessing.database.mongo_connection import (  # noqa: E402
    get_database,
    get_mongo_client,
    replace_collection_data,
)
from preprocessing.scripts.preprocessing_bank import preprocess_banking_data  # noqa: E402
from preprocessing.scripts.preprocessing_insurance import (  # noqa: E402
    preprocess_insurance_data,
)
from preprocessing.scripts.preprocessing_solar import preprocess_solar_data  # noqa: E402

DEFAULT_MONGO_URI = (
    "mongodb+srv://younes_dataviz:Mongo2026@examdataviz.h1v5vwa.mongodb.net/"
    "?appName=ExamDataviz"
)

LOGGER = logging.getLogger(__name__)


def configure_logging(log_level: str) -> None:
    """Configure the global logging policy for the ingestion script.

    Purpose:
        Provide readable execution logs for preprocessing, validation and
        MongoDB insertion.

    Inputs:
        log_level: Requested logging level (for example ``INFO`` or ``DEBUG``).

    Outputs:
        None. The Python logging module is configured in-place.
    """

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the ingestion workflow.

    Purpose:
        Allow the pipeline to be executed locally, with or without MongoDB
        insertion, while keeping sensible defaults for this project.

    Inputs:
        None. Arguments are read from ``sys.argv``.

    Outputs:
        The populated ``argparse.Namespace``.
    """

    parser = argparse.ArgumentParser(
        description="Preprocess bank, solar and insurance datasets, then ingest them into MongoDB.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Root directory containing data_bank, solar_data and insurance_data.",
    )
    parser.add_argument(
        "--mongo-uri",
        default=DEFAULT_MONGO_URI,
        help="MongoDB connection string used for ingestion.",
    )
    parser.add_argument(
        "--skip-mongo",
        action="store_true",
        help="Run preprocessing only, without inserting into MongoDB.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level to use during execution.",
    )
    return parser.parse_args()


def run_pipeline(project_root: Path, mongo_uri: str, skip_mongo: bool) -> dict[str, int]:
    """Execute the end-to-end preprocessing and ingestion pipeline.

    Purpose:
        Orchestrate the three domain preprocessors and optionally load their
        outputs into the target MongoDB collections.

    Inputs:
        project_root: Root project directory containing the data folders.
        mongo_uri: MongoDB connection string.
        skip_mongo: When ``True``, preprocessing is executed without database writes.

    Outputs:
        A dictionary summarizing the number of rows processed per dataset.
    """

    LOGGER.info("Starting data preprocessing pipeline from '%s'.", project_root)

    banking_dataframe = preprocess_banking_data(project_root / "data_bank")
    solar_dataframe = preprocess_solar_data(project_root / "solar_data")
    insurance_dataframe = preprocess_insurance_data(project_root / "insurance_data")

    summary = {
        "banking_rows": len(banking_dataframe),
        "solar_rows": len(solar_dataframe),
        "insurance_rows": len(insurance_dataframe),
    }

    LOGGER.info(
        "Preprocessing summary | banking=%s | solar=%s | insurance=%s",
        summary["banking_rows"],
        summary["solar_rows"],
        summary["insurance_rows"],
    )

    if skip_mongo:
        LOGGER.info("MongoDB insertion skipped by request.")
        return summary

    client = get_mongo_client(mongo_uri=mongo_uri)
    try:
        database = get_database(client, database_name="bank_dataviz")
        replace_collection_data(database, "banking_data", banking_dataframe)
        replace_collection_data(database, "solar_energy_data", solar_dataframe)
        replace_collection_data(database, "insurance_data", insurance_dataframe)
    finally:
        client.close()
        LOGGER.info("MongoDB connection closed.")

    return summary


def main() -> int:
    """CLI entry point for the ingestion workflow.

    Purpose:
        Expose the pipeline as an executable script with explicit error
        handling and readable logging.

    Inputs:
        None. Runtime configuration is taken from the command line.

    Outputs:
        Process exit code ``0`` on success, ``1`` on failure.
    """

    args = parse_arguments()
    configure_logging(args.log_level)

    try:
        run_pipeline(
            project_root=args.project_root,
            mongo_uri=args.mongo_uri,
            skip_mongo=args.skip_mongo,
        )
    except Exception as exc:
        LOGGER.exception("Pipeline execution failed: %s", exc)
        return 1

    LOGGER.info("Pipeline execution completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
