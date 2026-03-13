"""Solar dataset preprocessing utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd

LOGGER = logging.getLogger(__name__)

DIRECT_PRODUCTION_COLUMNS = {
    "production_kwh",
    "energy_produced",
    "solar_output",
    "production",
    "generation",
    "power_output",
}

DIRECT_CAPACITY_COLUMNS = {
    "capacity_kwh",
    "installed_capacity",
    "capacity",
    "panel_capacity",
}


def normalize_column_name(column_name: str) -> str:
    """Normalize a raw column name to snake_case.

    Purpose:
        Create a consistent schema across CSV variants and simplify downstream
        feature engineering.

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


def read_delimited_csv(csv_path: Path) -> pd.DataFrame:
    """Load a CSV file while auto-detecting the delimiter.

    Purpose:
        Support common CSV variations such as semicolon-separated files without
        hard-coding the delimiter per dataset.

    Inputs:
        csv_path: Path to the CSV file.

    Outputs:
        A loaded pandas DataFrame.
    """

    dataframe = pd.read_csv(csv_path, sep=None, engine="python")
    dataframe.columns = [normalize_column_name(column) for column in dataframe.columns]
    return dataframe


def convert_numeric_columns(dataframe: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Convert a list of columns to numeric values.

    Purpose:
        Guarantee that analytical features are computed on numeric pandas types.

    Inputs:
        dataframe: Input DataFrame.
        columns: Column names to convert when present.

    Outputs:
        The same DataFrame with converted numeric columns.
    """

    for column in columns:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")
    return dataframe


def min_max_scale(series: pd.Series) -> pd.Series:
    """Scale a numeric series between 0 and 1.

    Purpose:
        Provide comparable components for proxy feature engineering.

    Inputs:
        series: Numeric series to scale.

    Outputs:
        A scaled series between 0 and 1.
    """

    if series.empty or series.dropna().empty:
        return pd.Series([pd.NA] * len(series), index=series.index, dtype="Float64")

    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum) or minimum == maximum:
        return pd.Series([1.0] * len(series), index=series.index, dtype="Float64")

    return (series - minimum) / (maximum - minimum)


def build_weather_based_efficiency(dataframe: pd.DataFrame) -> pd.Series:
    """Create a solar production efficiency proxy from weather features.

    Purpose:
        Some source files contain weather measurements instead of explicit solar
        production. In that case, this function builds a transparent proxy that
        keeps the dashboard pipeline usable until a richer solar dataset is
        provided.

    Inputs:
        dataframe: Solar DataFrame after type conversion.

    Outputs:
        A ``production_efficiency`` proxy as a pandas Series.
    """

    components: list[pd.Series] = []

    if "meantemp" in dataframe.columns:
        components.append(min_max_scale(dataframe["meantemp"]))

    if "humidity" in dataframe.columns:
        components.append(1 - min_max_scale(dataframe["humidity"]))

    if "wind_speed" in dataframe.columns:
        components.append(1 - min_max_scale(dataframe["wind_speed"]))

    if "meanpressure" in dataframe.columns:
        pressure_delta = (dataframe["meanpressure"] - dataframe["meanpressure"].median()).abs()
        components.append(1 - min_max_scale(pressure_delta))

    if not components:
        raise ValueError(
            "The solar dataset does not contain enough columns to derive "
            "production_efficiency."
        )

    LOGGER.warning(
        "No direct solar production columns were detected. "
        "A weather-based efficiency proxy is being used."
    )
    stacked = pd.concat(components, axis=1)
    return stacked.mean(axis=1)


def compute_annual_growth(dataframe: pd.DataFrame, metric_column: str) -> pd.Series:
    """Compute annual growth for a selected metric.

    Purpose:
        Produce a dashboard-ready annual growth indicator while preserving the
        original row granularity.

    Inputs:
        dataframe: Solar DataFrame containing a ``year`` column.
        metric_column: Metric used to compute year-over-year growth.

    Outputs:
        A Series aligned with the input DataFrame index.
    """

    annual_metric = dataframe.groupby("year")[metric_column].mean().sort_index()
    annual_growth = annual_metric.pct_change().fillna(0.0)
    return dataframe["year"].map(annual_growth)


def preprocess_solar_data(data_directory: Path) -> pd.DataFrame:
    """Run the solar dataset preprocessing pipeline.

    Purpose:
        Clean the solar dataset, normalize the schema, compute the requested
        indicators and return a MongoDB-ready DataFrame.

    Inputs:
        data_directory: Directory containing ``solar_dataset.csv``.

    Outputs:
        A cleaned and enriched solar DataFrame.
    """

    csv_path = data_directory / "solar_dataset.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing solar dataset: {csv_path}")

    LOGGER.info("Loading solar dataset from '%s'.", csv_path)
    dataframe = read_delimited_csv(csv_path)

    if "date" not in dataframe.columns:
        raise ValueError("The solar dataset must contain a 'date' column.")

    dataframe["date"] = pd.to_datetime(
        dataframe["date"],
        errors="coerce",
        dayfirst=True,
    )

    numeric_candidates = [
        column
        for column in dataframe.columns
        if column != "date" and dataframe[column].dtype == "object"
    ]
    dataframe = convert_numeric_columns(dataframe, numeric_candidates)

    dataframe = dataframe.dropna(subset=["date"]).dropna(how="all")

    if DIRECT_PRODUCTION_COLUMNS.intersection(dataframe.columns):
        production_column = next(
            column for column in dataframe.columns if column in DIRECT_PRODUCTION_COLUMNS
        )

        if DIRECT_CAPACITY_COLUMNS.intersection(dataframe.columns):
            capacity_column = next(
                column for column in dataframe.columns if column in DIRECT_CAPACITY_COLUMNS
            )
            dataframe["production_efficiency"] = dataframe[production_column].divide(
                dataframe[capacity_column].replace({0: pd.NA})
            )
            dataframe["production_efficiency_source"] = "direct_ratio"
        else:
            dataframe["production_efficiency"] = min_max_scale(dataframe[production_column])
            dataframe["production_efficiency_source"] = "normalized_production"
    else:
        dataframe["production_efficiency"] = build_weather_based_efficiency(dataframe)
        dataframe["production_efficiency_source"] = "weather_proxy"

    dataframe = dataframe.dropna(subset=["production_efficiency"]).copy()
    dataframe["year"] = dataframe["date"].dt.year
    dataframe["month"] = dataframe["date"].dt.month
    dataframe["annual_growth"] = compute_annual_growth(dataframe, "production_efficiency")

    dataframe = dataframe.sort_values("date").reset_index(drop=True)
    LOGGER.info("Solar preprocessing completed with %s rows.", len(dataframe))
    return dataframe
