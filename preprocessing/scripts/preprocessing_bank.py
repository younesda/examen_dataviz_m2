"""Banking dataset preprocessing for Excel + BCEAO PDF sources."""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber

LOGGER = logging.getLogger(__name__)

MILLION_TO_FCFA = 1_000_000

PDF_SIGLE_ALIAS_TO_CANONICAL = {
    "SGSN": "SGBS",
    "BOAS": "BOA",
    "BCIMALI": "BCIM",
    "CBISENEGAL": "CBI",
    "BGFIBANK": "BGFI",
    "CI": "CISA",
}
PDF_NON_BANK_IDENTIFIERS = {
    "LOCAFRIQUE",
    "ALIOSFINANCE",
    "WAFACASH",
    "LAFINAO",
    "BBGCI",
}

IDENTIFIER_COLUMNS = ["sigle", "bank", "bank_name", "groupe_bancaire", "annee"]
BALANCE_COLUMNS = [
    "emploi",
    "bilan",
    "ressources",
    "fonds_propres",
    "effectif",
    "agence",
    "compte",
]
RESULTAT_COLUMNS = [
    "interets_et_produits_assimiles",
    "interets_et_charges_assimilees",
    "revenus_des_titres_a_revenu_variable",
    "commissions_produits",
    "commissions_charges",
    "gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_negociation",
    "gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_placement_et_assimiles",
    "autres_produits_d_exploitation_bancaire",
    "autres_charges_d_exploitation_bancaire",
    "produit_net_bancaire",
    "subventions_d_investissement",
    "charges_generales_d_exploitation",
    "dotations_aux_amortissements_et_aux_depreciations_des_immobilisations_incorporelles_et_corporelles",
    "resultat_brut_d_exploitation",
    "cout_du_risque",
    "resultat_exploitation",
    "gains_ou_pertes_nets_sur_actifs_immobilises",
    "resultat_avant_impot",
    "impots_sur_les_benefices",
    "resultat_net",
]
FINAL_BANK_COLUMNS = IDENTIFIER_COLUMNS + BALANCE_COLUMNS + RESULTAT_COLUMNS
MERGE_VALUE_COLUMNS = BALANCE_COLUMNS + RESULTAT_COLUMNS
MONETARY_COLUMNS = [column for column in MERGE_VALUE_COLUMNS if column not in {"effectif", "agence", "compte"}]
PDF_ZERO_DEFAULT_COLUMNS = [
    "revenus_des_titres_a_revenu_variable",
    "gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_placement_et_assimiles",
    "autres_charges_d_exploitation_bancaire",
    "subventions_d_investissement",
]

PDF_LABEL_TO_COLUMN = {
    "bilan": {
        "creances sur la clientele": "emploi",
        "total de l actif": "bilan",
        "dettes a l egard de la clientele": "ressources",
        "dettes a legard de la clientele": "ressources",
        "capitaux propres et ressources assimilees": "fonds_propres",
    },
    "resultats": {
        "interets et produits assimiles": "interets_et_produits_assimiles",
        "interets et charges assimilees": "interets_et_charges_assimilees",
        "revenus des titres a revenu variable": "revenus_des_titres_a_revenu_variable",
        "commissions produits": "commissions_produits",
        "commissions charges": "commissions_charges",
        "gains ou pertes nets sur operations des portefeuilles de negociation": "gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_negociation",
        "gains ou pertes nets sur operations des portefeuilles de placement et assimiles": "gains_ou_pertes_nets_sur_operations_des_portefeuilles_de_placement_et_assimiles",
        "autres produits d exploitation bancaire": "autres_produits_d_exploitation_bancaire",
        "autres charges d exploitation bancaire": "autres_charges_d_exploitation_bancaire",
        "produit net bancaire": "produit_net_bancaire",
        "subventions d investissement": "subventions_d_investissement",
        "charges generales d exploitation": "charges_generales_d_exploitation",
        "dotation aux amortissements et aux depreciations des immobilisations incorporelles et corporelles": "dotations_aux_amortissements_et_aux_depreciations_des_immobilisations_incorporelles_et_corporelles",
        "resultat brut d exploitation": "resultat_brut_d_exploitation",
        "cout du risque": "cout_du_risque",
        "resultat d exploitation": "resultat_exploitation",
        "gains ou pertes nets sur actifs immobilises": "gains_ou_pertes_nets_sur_actifs_immobilises",
        "resultat avant impot": "resultat_avant_impot",
        "impots sur les benefices": "impots_sur_les_benefices",
        "resultat net": "resultat_net",
    },
}


def normalize_text(value: str) -> str:
    """Normalize free text for resilient matching.

    Purpose:
        Remove accents and punctuation differences so the same business label can
        be matched reliably across Excel headers, PDF text and code mappings.

    Inputs:
        value: Raw text to normalize.

    Outputs:
        A lowercase, accent-free and punctuation-light string.
    """

    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_column_name(column_name: str) -> str:
    """Convert an input column name into snake_case.

    Purpose:
        Standardise column names from heterogeneous sources so downstream code
        can stay explicit and predictable.

    Inputs:
        column_name: Original column name.

    Outputs:
        The normalized snake_case column name.
    """

    normalized = normalize_text(column_name).replace(" ", "_")
    correction_map = {
        "goupe_bancaire": "groupe_bancaire",
        "fonds_propre": "fonds_propres",
        "nterets_et_charges_assimilees": "interets_et_charges_assimilees",
        "resultat_d_exploitation": "resultat_exploitation",
        "resultat_net": "resultat_net",
        "produit_net_bancaire": "produit_net_bancaire",
    }
    return correction_map.get(normalized, normalized)


def normalize_identifier(value: Any) -> str:
    """Normalize a bank code into a punctuation-free uppercase identifier."""

    return normalize_text(value).replace(" ", "").upper()



def slugify_identifier(value: Any) -> str:
    """Build a stable snake_case slug from a bank identifier."""

    return normalize_text(value).replace(" ", "_")



def clean_sigle_label(value: Any) -> str:
    """Clean a sigle label while preserving business punctuation when useful."""

    cleaned = re.sub(r"\s+", " ", str(value)).strip().upper()
    cleaned = re.sub(r"\s*-\s*", "-", cleaned)
    cleaned = re.sub(r"\.+", ".", cleaned)
    return cleaned.strip(". ")



def clean_pdf_bank_name(value: Any) -> str:
    """Normalize a bank legal name extracted from the BCEAO PDF header."""

    cleaned = re.sub(r"\(\*\)", "", str(value))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -*")
    return cleaned



def build_excel_sigle_lookup(excel_dataframe: pd.DataFrame) -> dict[str, str]:
    """Map normalized Excel sigles back to their canonical workbook sigles."""

    return {
        normalize_identifier(sigle): str(sigle).strip().upper()
        for sigle in excel_dataframe["sigle"].dropna().astype(str)
    }



def clean_numeric_value(value: Any) -> float | None:
    """Convert a raw numeric value into a Python float.

    Purpose:
        Harmonise Excel values, PDF strings and CSV strings into a single numeric
        representation while preserving missing values.

    Inputs:
        value: Raw value to parse.

    Outputs:
        A float when conversion succeeds, otherwise ``None``.
    """

    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    text = text.replace("(", "").replace(")", "")
    text = text.replace("\u202f", " ").replace("\xa0", " ").replace(" ", "")
    text = text.replace(",", ".")

    try:
        parsed_value = float(text)
    except ValueError:
        LOGGER.debug("Unable to parse numeric value '%s'.", value)
        return None

    return -parsed_value if negative else parsed_value


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Perform a division while protecting against zero denominators.

    Purpose:
        Compute dashboard ratios without creating infinite values that would be
        problematic for storage and visualisation.

    Inputs:
        numerator: Series used as numerator.
        denominator: Series used as denominator.

    Outputs:
        A pandas Series containing the computed ratio.
    """

    denominator = denominator.replace({0: pd.NA})
    return numerator.divide(denominator)


def ensure_boolean_series(dataframe: pd.DataFrame, column_name: str) -> pd.Series:
    """Return a DataFrame column as a clean boolean Series.

    Purpose:
        Normalize merge-origin flags without triggering pandas downcasting
        warnings during fill operations.

    Inputs:
        dataframe: DataFrame containing the column.
        column_name: Column name to coerce.

    Outputs:
        A boolean Series aligned with the DataFrame index.
    """

    if column_name not in dataframe.columns:
        return pd.Series(False, index=dataframe.index, dtype=bool)

    return dataframe[column_name].astype("boolean").fillna(False).astype(bool)


def fill_sparse_pdf_result_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Fill sparse BCEAO result lines that implicitly represent zeros.

    Purpose:
        Some BCEAO pages omit repeated zero values and leave blank spaces instead
        of printing all year columns. For the affected result-line items, PDF
        rows are therefore completed with explicit zeros before MongoDB storage.

    Inputs:
        dataframe: Merged banking DataFrame containing the ``source_pdf`` flag.

    Outputs:
        The same DataFrame with sparse PDF result gaps filled with zeros.
    """

    pdf_mask = ensure_boolean_series(dataframe, "source_pdf")
    dataframe.loc[pdf_mask, PDF_ZERO_DEFAULT_COLUMNS] = (
        dataframe.loc[pdf_mask, PDF_ZERO_DEFAULT_COLUMNS].fillna(0)
    )
    return dataframe


def load_bank_excel(excel_path: Path) -> pd.DataFrame:
    """Load and normalize the official Senegal banking Excel file.

    Purpose:
        Use the Excel workbook as the reference schema, clean the relevant
        banking indicators, and preserve every bank available in the source.

    Inputs:
        excel_path: Path to ``BASE_SENEGAL2.xlsx``.

    Outputs:
        A cleaned DataFrame aligned on the target bank schema.
    """

    LOGGER.info("Loading banking Excel source from '%s'.", excel_path)
    dataframe = pd.read_excel(excel_path)
    dataframe.columns = [normalize_column_name(column) for column in dataframe.columns]

    required_columns = ["sigle", "groupe_bancaire", "annee"] + BALANCE_COLUMNS + RESULTAT_COLUMNS
    missing_columns = [column for column in required_columns if column not in dataframe.columns]
    if missing_columns:
        raise ValueError(
            "The banking Excel file is missing required columns: "
            + ", ".join(missing_columns)
        )

    dataframe = dataframe[required_columns].copy()
    dataframe["sigle"] = dataframe["sigle"].astype(str).str.strip().str.upper()
    dataframe = dataframe[dataframe["sigle"].ne("")].copy()

    for column in required_columns:
        if column not in {"sigle", "groupe_bancaire"}:
            dataframe[column] = dataframe[column].apply(clean_numeric_value)

    dataframe["annee"] = dataframe["annee"].astype("Int64")
    dataframe["bank"] = dataframe["sigle"].map(slugify_identifier)
    dataframe["bank_name"] = dataframe["sigle"]

    for column in MONETARY_COLUMNS:
        dataframe[column] = dataframe[column].apply(
            lambda value: value * MILLION_TO_FCFA if value is not None else None
        )

    dataframe["source_excel"] = True
    LOGGER.info(
        "Banking Excel preprocessing completed with %s rows across %s banks.",
        len(dataframe),
        dataframe["sigle"].nunique(),
    )
    return dataframe


def split_pdf_line(line: str) -> list[str]:
    """Split a PDF text line into aligned columns.

    Purpose:
        PDF text extracted with ``layout=True`` preserves horizontal spacing.
        Splitting on repeated spaces allows us to recover table columns without
        depending on fragile full-table extraction.

    Inputs:
        line: Raw text line extracted from the PDF.

    Outputs:
        A list of cleaned columns found on the line.
    """

    return [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]


def extract_numeric_values_from_line(line: str, years_count: int) -> list[float | None] | None:
    """Extract a numeric year vector from one PDF line.

    Purpose:
        Recognize lines that contain only yearly values, which is common when a
        long BCEAO label is wrapped onto adjacent lines.

    Inputs:
        line: Raw PDF line.
        years_count: Number of years expected on the page.

    Outputs:
        A list of parsed numeric values, or ``None`` if the line is not purely numeric.
    """

    parts = split_pdf_line(line)
    if len(parts) < years_count:
        return None

    numeric_values = [clean_numeric_value(part) for part in parts[:years_count]]
    if any(value is None for value in numeric_values):
        return None

    return numeric_values


def identify_target_bank(
    lines: list[str],
    excel_sigle_lookup: dict[str, str],
) -> tuple[str | None, str | None]:
    """Identify the canonical Senegal bank represented on a PDF page.

    Purpose:
        Resolve the bank sigle shown in the PDF header, align it with the Excel
        workbook sigles when possible, and skip non-bank institutions.

    Inputs:
        lines: Text lines extracted from a single PDF page.
        excel_sigle_lookup: Mapping of normalized Excel sigles to canonical sigles.

    Outputs:
        A tuple containing the canonical sigle and a readable bank name.
    """

    if len(lines) < 4:
        return None, None

    raw_identifier = lines[1]
    normalized_identifier = normalize_identifier(raw_identifier)
    if normalize_text(raw_identifier).startswith(("banques", "etablissements")):
        return None, None
    if normalized_identifier in PDF_NON_BANK_IDENTIFIERS:
        return None, None

    canonical_sigle = PDF_SIGLE_ALIAS_TO_CANONICAL.get(normalized_identifier)
    if canonical_sigle is None:
        canonical_sigle = excel_sigle_lookup.get(normalized_identifier)
    if canonical_sigle is None:
        canonical_sigle = clean_sigle_label(raw_identifier)

    full_name = clean_pdf_bank_name(lines[3] if len(lines) > 3 else raw_identifier)
    return canonical_sigle, full_name or canonical_sigle


def extract_years_from_page(lines: list[str]) -> list[int]:
    """Extract the reporting years declared on a PDF page.

    Purpose:
        Determine the year columns used by the BCEAO page so parsed values can
        be written back to the correct annual record.

    Inputs:
        lines: PDF page lines.

    Outputs:
        A list of years, typically ``[2020, 2021, 2022]``.
    """

    for line in lines[:10]:
        years = re.findall(r"\b20\d{2}\b", line)
        if len(years) >= 2:
            return [int(year) for year in years]
    return []


def is_target_senegal_page(lines: list[str]) -> bool:
    """Check whether a PDF page belongs to the Senegal bank section.

    Purpose:
        Exclude the table of contents and other UMOA countries before applying
        bank-level parsing logic.

    Inputs:
        lines: PDF page lines.

    Outputs:
        ``True`` for Senegal bank detail pages, otherwise ``False``.
    """

    return bool(lines) and normalize_text(lines[0]) == "senegal"


def parse_pdf_page_metrics(
    page_text: str,
    excel_sigle_lookup: dict[str, str],
) -> tuple[str | None, str | None, str | None, dict[int, dict[str, float | None]]]:
    """Parse the banking metrics needed from one BCEAO PDF page.

    Purpose:
        Extract both the balance-sheet metrics and the detailed income-statement
        metrics needed to complete the Excel dataset.

    Inputs:
        page_text: Full text extracted from a single PDF page.
        excel_sigle_lookup: Mapping of normalized Excel sigles to canonical sigles.

    Outputs:
        A tuple containing the canonical sigle, bank name, page type and a
        year-indexed dictionary of extracted metrics.
    """

    lines = [line for line in page_text.splitlines() if line.strip()]
    if not is_target_senegal_page(lines):
        return None, None, None, {}

    normalized_page = normalize_text(page_text)
    if "bilans" in normalized_page:
        page_type = "bilan"
    elif "comptes de resultat" in normalized_page:
        page_type = "resultats"
    else:
        return None, None, None, {}

    sigle, bank_name = identify_target_bank(lines, excel_sigle_lookup)
    if sigle is None:
        return None, None, None, {}

    years = extract_years_from_page(lines)
    if not years:
        LOGGER.warning("No year header detected for bank '%s' on one PDF page.", sigle)
        return sigle, bank_name, page_type, {}

    metrics_by_year: dict[int, dict[str, float | None]] = {year: {} for year in years}
    expected_labels = PDF_LABEL_TO_COLUMN[page_type]
    years_count = len(years)

    index = 0
    while index < len(lines):
        line = lines[index]
        parts = split_pdf_line(line)
        if not parts:
            index += 1
            continue

        if len(parts) >= years_count + 1:
            label = normalize_text(parts[0])
            numeric_values = [clean_numeric_value(value) for value in parts[1 : 1 + years_count]]
            if label in expected_labels and all(value is not None for value in numeric_values):
                target_column = expected_labels[label]
                for year, raw_value in zip(years, numeric_values):
                    metrics_by_year[year][target_column] = raw_value * MILLION_TO_FCFA
            index += 1
            continue

        if len(parts) == 1 and index + 1 < len(lines):
            numeric_values = extract_numeric_values_from_line(lines[index + 1], years_count)
            if numeric_values is not None:
                candidate_labels = [normalize_text(parts[0])]
                consumed_lines = 2

                if index + 2 < len(lines):
                    suffix_values = extract_numeric_values_from_line(lines[index + 2], years_count)
                    suffix_parts = split_pdf_line(lines[index + 2])
                    if suffix_values is None and len(suffix_parts) == 1:
                        candidate_labels.insert(
                            0,
                            normalize_text(parts[0] + " " + suffix_parts[0]),
                        )
                        consumed_lines = 3

                matched_label = next(
                    (label for label in candidate_labels if label in expected_labels),
                    None,
                )
                if matched_label is not None:
                    target_column = expected_labels[matched_label]
                    for year, raw_value in zip(years, numeric_values):
                        metrics_by_year[year][target_column] = raw_value * MILLION_TO_FCFA
                    index += consumed_lines
                    continue

        index += 1

    return sigle, bank_name, page_type, metrics_by_year


def extract_pdf_bank_data(
    pdf_path: Path,
    excel_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Extract target Senegal bank metrics from the BCEAO PDF.

    Purpose:
        Read the BCEAO publication, keep every Senegal bank page, convert the
        amounts from millions of FCFA to FCFA, and return a merge-ready annual
        DataFrame.

    Inputs:
        pdf_path: Path to ``bilans_bceao.pdf``.
        excel_dataframe: Clean Excel data used to align PDF sigles.

    Outputs:
        A DataFrame containing the extracted PDF metrics by bank and year.
    """

    LOGGER.info("Extracting complementary banking data from '%s'.", pdf_path)
    records: dict[tuple[str, int], dict[str, Any]] = {}
    excel_sigle_lookup = build_excel_sigle_lookup(excel_dataframe)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text(layout=True) or ""
            sigle, bank_name, page_type, metrics_by_year = parse_pdf_page_metrics(
                page_text,
                excel_sigle_lookup,
            )

            if sigle is None or not metrics_by_year:
                continue

            for year, metrics in metrics_by_year.items():
                record_key = (sigle, year)
                record = records.setdefault(
                    record_key,
                    {
                        "sigle": sigle,
                        "bank": slugify_identifier(sigle),
                        "bank_name": bank_name or sigle,
                        "annee": year,
                        "source_pdf": True,
                    },
                )
                if bank_name:
                    record["bank_name"] = bank_name
                record.update(metrics)

            LOGGER.debug(
                "Parsed banking PDF page %s for bank '%s' (%s).",
                page_number,
                sigle,
                page_type,
            )

    dataframe = pd.DataFrame(records.values())
    if dataframe.empty:
        raise ValueError("No target Senegal banking records were extracted from the PDF.")

    LOGGER.info(
        "Banking PDF extraction completed with %s rows across %s banks.",
        len(dataframe),
        dataframe["sigle"].nunique(),
    )
    return dataframe


def build_group_mapping(excel_dataframe: pd.DataFrame) -> dict[str, str]:
    """Build a stable bank-group mapping from the Excel source.

    Purpose:
        Reuse the official Excel group labels for PDF-only years so the merged
        dataset stays dimensionally consistent.

    Inputs:
        excel_dataframe: Cleaned Excel DataFrame.

    Outputs:
        A dictionary keyed by sigle with one banking-group value per bank.
    """

    group_mapping: dict[str, str] = {}

    for sigle, group_series in excel_dataframe.groupby("sigle")["groupe_bancaire"]:
        non_null_values = group_series.dropna()
        if non_null_values.empty:
            continue
        group_mapping[sigle] = non_null_values.mode().iloc[0]

    return group_mapping


def merge_bank_sources(
    excel_dataframe: pd.DataFrame,
    pdf_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Merge the Excel and PDF banking sources into one enriched dataset.

    Purpose:
        Keep the Excel file as the official structure while using the BCEAO PDF
        to complete missing metrics and extend the dataset when extra PDF years
        are available.

    Inputs:
        excel_dataframe: Cleaned banking Excel DataFrame.
        pdf_dataframe: Cleaned banking PDF DataFrame.

    Outputs:
        A merged DataFrame containing normalized and enriched banking data.
    """

    LOGGER.info("Merging banking Excel and PDF datasets.")
    merged = excel_dataframe.merge(
        pdf_dataframe,
        on=["sigle", "annee"],
        how="outer",
        suffixes=("_excel", "_pdf"),
    )

    group_mapping = build_group_mapping(excel_dataframe)
    merged["groupe_bancaire"] = merged.get(
        "groupe_bancaire_excel",
        pd.Series(index=merged.index, dtype="object"),
    )
    merged["groupe_bancaire"] = merged["groupe_bancaire"].fillna(
        merged["sigle"].map(group_mapping)
    )
    merged["bank"] = merged.get("bank_excel", pd.Series(index=merged.index, dtype="object"))
    merged["bank"] = merged["bank"].combine_first(
        merged.get("bank_pdf", pd.Series(index=merged.index, dtype="object"))
    )
    merged["bank"] = merged["bank"].fillna(merged["sigle"].map(slugify_identifier))
    merged["bank_name"] = merged.get("bank_name_pdf", pd.Series(index=merged.index, dtype="object"))
    merged["bank_name"] = merged["bank_name"].combine_first(
        merged.get("bank_name_excel", pd.Series(index=merged.index, dtype="object"))
    )
    merged["bank_name"] = merged["bank_name"].fillna(merged["sigle"])

    stable_name_mapping = (
        merged[["sigle", "bank_name"]]
        .dropna(subset=["bank_name"])
        .assign(name_length=lambda frame: frame["bank_name"].astype(str).str.len())
        .sort_values(["sigle", "name_length"], ascending=[True, False], kind="stable")
        .drop_duplicates(subset=["sigle"])
        .set_index("sigle")["bank_name"]
        .to_dict()
    )
    merged["bank_name"] = merged["sigle"].map(stable_name_mapping).fillna(merged["bank_name"])

    for column in MERGE_VALUE_COLUMNS:
        excel_column = f"{column}_excel"
        pdf_column = f"{column}_pdf"

        if excel_column in merged.columns and pdf_column in merged.columns:
            merged[column] = merged[excel_column].combine_first(merged[pdf_column])
        elif excel_column in merged.columns:
            merged[column] = merged[excel_column]
        elif pdf_column in merged.columns:
            merged[column] = merged[pdf_column]

    merged["source_excel"] = ensure_boolean_series(merged, "source_excel")
    merged["source_pdf"] = ensure_boolean_series(merged, "source_pdf")
    merged = fill_sparse_pdf_result_columns(merged)

    merged["record_origin"] = merged.apply(
        lambda row: (
            "excel_and_pdf"
            if row["source_excel"] and row["source_pdf"]
            else "excel"
            if row["source_excel"]
            else "pdf"
        ),
        axis=1,
    )

    merged["ratio_fonds_propres"] = safe_divide(merged["fonds_propres"], merged["bilan"])
    merged["ratio_ressources"] = safe_divide(merged["ressources"], merged["bilan"])
    merged["rentabilite"] = safe_divide(merged["resultat_net"], merged["bilan"])
    merged["annee"] = merged["annee"].astype("Int64")

    final_columns = FINAL_BANK_COLUMNS + [
        "ratio_fonds_propres",
        "ratio_ressources",
        "rentabilite",
        "source_excel",
        "source_pdf",
        "record_origin",
    ]

    merged = merged[final_columns].sort_values(["bank", "annee"]).reset_index(drop=True)
    LOGGER.info("Final banking dataset contains %s rows.", len(merged))
    return merged


def preprocess_banking_data(data_directory: Path) -> pd.DataFrame:
    """Run the full banking preprocessing pipeline.

    Purpose:
        Load the Excel schema, complement it with BCEAO PDF values for the
        Senegal target banks, compute business ratios, and return a MongoDB-ready
        dataset.

    Inputs:
        data_directory: Directory containing ``BASE_SENEGAL2.xlsx`` and
            ``bilans_bceao.pdf``.

    Outputs:
        A cleaned and enriched banking DataFrame.
    """

    excel_path = data_directory / "BASE_SENEGAL2.xlsx"
    pdf_path = data_directory / "bilans_bceao.pdf"

    if not excel_path.exists():
        raise FileNotFoundError(f"Missing Excel source: {excel_path}")
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing PDF source: {pdf_path}")

    excel_dataframe = load_bank_excel(excel_path)
    pdf_dataframe = extract_pdf_bank_data(pdf_path, excel_dataframe)
    merged_dataframe = merge_bank_sources(excel_dataframe, pdf_dataframe)

    validation_dataframe = merged_dataframe.assign(
        company=merged_dataframe["bank_name"],
        year=merged_dataframe["annee"],
    )
    print("Total rows:", len(validation_dataframe))
    print("Unique banks:", validation_dataframe["company"].nunique())
    print("Years:", [int(year) for year in sorted(validation_dataframe["year"].dropna().astype(int).unique())])
    print(validation_dataframe.groupby("year")["company"].nunique())

    return merged_dataframe
