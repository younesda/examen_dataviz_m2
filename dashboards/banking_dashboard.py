"""Callbacks for the advanced banking dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State

from dashboards.utils import (
    ALL_FILTER_VALUE,
    build_dropdown_options,
    create_empty_figure,
    filter_dataframe,
    format_number,
    style_figure,
)

PLOT_TEMPLATE = "plotly_dark"
COLOR_SEQUENCE = [
    "#38bdf8",
    "#7dd3fc",
    "#22c55e",
    "#f59e0b",
    "#fb7185",
    "#a78bfa",
    "#f97316",
    "#34d399",
    "#facc15",
    "#60a5fa",
    "#c084fc",
]
NUMERIC_COLUMNS = [
    "year",
    "bilan",
    "ressources",
    "fonds_propres",
    "produit_net_bancaire",
    "resultat_exploitation",
    "resultat_net",
    "effectif",
    "agence",
    "compte",
]
SNAPSHOT_SUM_COLUMNS = [
    "bilan",
    "ressources",
    "fonds_propres",
    "compte",
]
FLOW_SUM_COLUMNS = [
    "produit_net_bancaire",
    "resultat_exploitation",
    "resultat_net",
]
SUM_COLUMNS = [*SNAPSHOT_SUM_COLUMNS, *FLOW_SUM_COLUMNS]
AVERAGE_COLUMNS = ["effectif", "agence"]
BANKING_LABELS = {
    "company": "Bank",
    "year": "Year",
    "bilan": "Total Assets (FCFA)",
    "fonds_propres": "Fonds Propres (FCFA)",
    "produit_net_bancaire": "Produit Net Bancaire (FCFA)",
    "resultat_net": "Resultat Net (FCFA)",
    "resultat_exploitation": "Resultat d'exploitation (FCFA)",
    "effectif": "Headcount",
    "agence": "Branches",
    "compte": "Accounts",
}



def _sum_with_min_count(series: pd.Series) -> float:
    """Aggregate a numeric series while preserving all-null groups.

    Purpose:
        Keep grouped sums faithful to the original data by returning missing
        values when a group contains no usable numeric observations.

    Inputs:
        series: Numeric pandas Series.

    Outputs:
        The grouped sum or ``pd.NA`` when every value is missing.
    """

    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.dropna().empty:
        return pd.NA
    return float(numeric_series.sum(min_count=1))



def _mean_with_min_count(series: pd.Series) -> float:
    """Aggregate a numeric series using a null-aware mean.

    Purpose:
        Average operational metrics such as branches and headcount without
        forcing zeroes when a group has no valid values.

    Inputs:
        series: Numeric pandas Series.

    Outputs:
        The grouped mean or ``pd.NA`` when every value is missing.
    """

    numeric_series = pd.to_numeric(series, errors="coerce")
    if numeric_series.dropna().empty:
        return pd.NA
    return float(numeric_series.mean())



def _prepare_banking_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Prepare the banking DataFrame for in-memory dashboard filtering.

    Purpose:
        Convert expected numeric fields once at startup so callbacks only need
        to filter and aggregate data already kept in memory.

    Inputs:
        dataframe: Raw banking DataFrame loaded from MongoDB.

    Outputs:
        A copied and type-normalized banking DataFrame.
    """

    prepared = dataframe.copy()

    if "company" in prepared.columns:
        prepared["company"] = prepared["company"].fillna("Unknown Bank").astype(str).str.strip()

    for column in NUMERIC_COLUMNS:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    if "year" in prepared.columns:
        prepared["year"] = prepared["year"].astype("Int64")

    return prepared



def _select_latest_year_snapshot(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Keep only the latest available year inside the current filter scope.

    Purpose:
        Prevent stock metrics such as total assets or equity from being summed
        across multiple fiscal years when the dashboard is viewed on "All years".

    Inputs:
        dataframe: Filtered banking DataFrame.

    Outputs:
        The latest-year slice of the provided DataFrame when possible.
    """

    if dataframe.empty or "year" not in dataframe.columns:
        return dataframe.copy()

    with_years = dataframe.dropna(subset=["year"]).copy()
    if with_years.empty:
        return dataframe.copy()

    latest_year = with_years["year"].max()
    return with_years[with_years["year"] == latest_year].copy()



def _aggregate_company_metrics(
    dataframe: pd.DataFrame,
    sum_columns: list[str],
    average_columns: list[str],
) -> pd.DataFrame:
    """Aggregate company metrics with explicit sum and mean strategies.

    Purpose:
        Reuse one null-aware grouping helper for both stock snapshots and
        multi-year flow metrics.

    Inputs:
        dataframe: Banking DataFrame already filtered to the desired scope.
        sum_columns: Numeric columns aggregated with a sum.
        average_columns: Numeric columns aggregated with a mean.

    Outputs:
        A company-level aggregated DataFrame.
    """

    if dataframe.empty or "company" not in dataframe.columns:
        return pd.DataFrame(columns=["company", *sum_columns, *average_columns])

    aggregation_map: dict[str, Any] = {}
    for column in sum_columns:
        if column in dataframe.columns:
            aggregation_map[column] = _sum_with_min_count
    for column in average_columns:
        if column in dataframe.columns:
            aggregation_map[column] = _mean_with_min_count

    if not aggregation_map:
        return (
            dataframe[["company"]]
            .drop_duplicates()
            .sort_values("company", kind="stable")
            .reset_index(drop=True)
        )

    aggregated = (
        dataframe.groupby("company", dropna=True, as_index=False)
        .agg(aggregation_map)
        .sort_values("company", kind="stable")
        .reset_index(drop=True)
    )

    for column in [*sum_columns, *average_columns]:
        if column in aggregated.columns:
            aggregated[column] = pd.to_numeric(aggregated[column], errors="coerce")

    return aggregated



def _aggregate_by_company(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the filtered banking data at bank level.

    Purpose:
        Provide one comparable record per bank for KPI-adjacent charts and the
        ranking table.

    Inputs:
        dataframe: Filtered banking DataFrame.

    Outputs:
        A bank-level aggregated DataFrame.
    """

    if dataframe.empty or "company" not in dataframe.columns:
        return pd.DataFrame(columns=["company", *SUM_COLUMNS, *AVERAGE_COLUMNS])

    latest_year_snapshot = _select_latest_year_snapshot(dataframe)
    snapshot_summary = _aggregate_company_metrics(
        latest_year_snapshot,
        sum_columns=SNAPSHOT_SUM_COLUMNS,
        average_columns=AVERAGE_COLUMNS,
    )
    flow_summary = _aggregate_company_metrics(
        dataframe,
        sum_columns=FLOW_SUM_COLUMNS,
        average_columns=[],
    )

    aggregated = snapshot_summary.merge(flow_summary, on="company", how="outer")

    for column in [*SUM_COLUMNS, *AVERAGE_COLUMNS]:
        if column in aggregated.columns:
            aggregated[column] = pd.to_numeric(aggregated[column], errors="coerce")

    if "bilan" in aggregated.columns:
        aggregated = aggregated.sort_values("bilan", ascending=False, kind="stable").reset_index(drop=True)

    return aggregated



def _aggregate_by_company_and_year(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the filtered banking data at bank-year granularity.

    Purpose:
        Create a stable analytical base for time-series and bubble charts where
        one point should represent one bank in one year.

    Inputs:
        dataframe: Filtered banking DataFrame.

    Outputs:
        A bank-year aggregated DataFrame sorted chronologically.
    """

    required_columns = {"company", "year"}
    if dataframe.empty or not required_columns.issubset(dataframe.columns):
        return pd.DataFrame(columns=["company", "year", *SUM_COLUMNS, *AVERAGE_COLUMNS])

    with_years = dataframe.dropna(subset=["year"]).copy()
    if with_years.empty:
        return pd.DataFrame(columns=["company", "year", *SUM_COLUMNS, *AVERAGE_COLUMNS])

    aggregation_map: dict[str, Any] = {}
    for column in SUM_COLUMNS:
        if column in with_years.columns:
            aggregation_map[column] = _sum_with_min_count
    for column in AVERAGE_COLUMNS:
        if column in with_years.columns:
            aggregation_map[column] = _mean_with_min_count

    aggregated = (
        with_years.groupby(["year", "company"], dropna=True, as_index=False)
        .agg(aggregation_map)
        .sort_values(["year", "company"], kind="stable")
        .reset_index(drop=True)
    )

    for column in [*SUM_COLUMNS, *AVERAGE_COLUMNS]:
        if column in aggregated.columns:
            aggregated[column] = pd.to_numeric(aggregated[column], errors="coerce")

    aggregated["year"] = aggregated["year"].astype(int)
    return aggregated



def _format_kpi_metric(
    dataframe: pd.DataFrame,
    metric_column: str,
    *,
    snapshot_latest_year: bool = False,
    suffix: str = " FCFA",
) -> str:
    """Format one KPI metric from either the full selection or its latest year.

    Purpose:
        Keep the main callback readable while making stock-vs-flow KPI behavior
        explicit and testable.

    Inputs:
        dataframe: Filtered banking DataFrame.
        metric_column: Numeric column to aggregate.
        snapshot_latest_year: Whether the KPI should use the latest-year slice.
        suffix: Text appended to the formatted KPI.

    Outputs:
        A human-readable KPI string.
    """

    source_frame = _select_latest_year_snapshot(dataframe) if snapshot_latest_year else dataframe
    if source_frame.empty or metric_column not in source_frame.columns:
        return "N/A"

    return format_number(source_frame[metric_column].sum(min_count=1), suffix=suffix)



def _ensure_size_column(dataframe: pd.DataFrame, source_column: str, target_column: str) -> pd.DataFrame:
    """Build a positive marker-size column for bubble charts.

    Purpose:
        Guarantee valid Plotly bubble sizes even when the source metric contains
        null values or negative numbers.

    Inputs:
        dataframe: DataFrame receiving the new size column.
        source_column: Source numeric metric.
        target_column: Name of the generated positive size column.

    Outputs:
        The same DataFrame with a positive marker-size field.
    """

    sized = dataframe.copy()
    if source_column not in sized.columns:
        sized[target_column] = 1.0
        return sized

    sized[target_column] = pd.to_numeric(sized[source_column], errors="coerce").abs().fillna(1.0).clip(lower=1.0)
    return sized



def _apply_chart_styling(
    figure: go.Figure,
    title: str,
    x_title: str | None = None,
    y_title: str | None = None,
    height: int = 360,
    hovermode: str = "closest",
) -> go.Figure:
    """Apply shared styling rules to banking charts.

    Purpose:
        Keep all banking visuals consistent with the app's dark professional
        dashboard theme and readable across tabs.

    Inputs:
        figure: Plotly figure to style.
        title: Chart title.
        x_title: Optional x-axis title.
        y_title: Optional y-axis title.
        height: Figure height in pixels.
        hovermode: Plotly hover interaction mode.

    Outputs:
        The styled figure.
    """

    figure.update_layout(
        template=PLOT_TEMPLATE,
        colorway=COLOR_SEQUENCE,
        height=height,
        hovermode=hovermode,
        legend_title_text="",
        transition_duration=250,
    )
    figure = style_figure(figure, title)

    if x_title:
        figure.update_xaxes(title=x_title)
    if y_title:
        figure.update_yaxes(title=y_title)

    return figure



def _build_market_share_figure(company_summary: pd.DataFrame) -> go.Figure:
    """Build the market share pie chart.

    Purpose:
        Show how total assets are distributed across the selected banking
        perimeter.

    Inputs:
        company_summary: Bank-level aggregated banking data.

    Outputs:
        A styled Plotly pie chart.
    """

    if company_summary.empty or "bilan" not in company_summary.columns or company_summary["bilan"].dropna().empty:
        return create_empty_figure("Market Share by Total Assets", "No asset data available for the selected filters.")

    figure = px.pie(
        company_summary,
        values="bilan",
        names="company",
        hole=0.45,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    figure.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Total assets: %{value:,.0f} FCFA<br>Market share: %{percent}<extra></extra>",
    )
    return _apply_chart_styling(figure, "Market Share by Total Assets")



def _build_sector_evolution_figure(company_year_summary: pd.DataFrame) -> go.Figure:
    """Build the sector evolution line chart.

    Purpose:
        Highlight the time evolution of total assets by bank across the current
        selection.

    Inputs:
        company_year_summary: Bank-year aggregated banking data.

    Outputs:
        A styled Plotly line chart.
    """

    if company_year_summary.empty or "bilan" not in company_year_summary.columns:
        return create_empty_figure("Sector Evolution Over Time", "No historical asset data available for this selection.")

    figure = px.line(
        company_year_summary,
        x="year",
        y="bilan",
        color="company",
        markers=True,
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
        hover_data={"year": True, "bilan": ":,.0f", "company": True},
    )
    figure.update_traces(mode="lines+markers")
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(
        figure,
        "Sector Evolution Over Time",
        x_title="Year",
        y_title="Total Assets (FCFA)",
        hovermode="x unified",
    )



def _build_top_banks_figure(company_summary: pd.DataFrame) -> go.Figure:
    """Build the top-banks bar chart.

    Purpose:
        Rank the largest banks in the selected perimeter by total assets.

    Inputs:
        company_summary: Bank-level aggregated banking data.

    Outputs:
        A styled Plotly bar chart.
    """

    if company_summary.empty or "bilan" not in company_summary.columns:
        return create_empty_figure("Top Banks by Total Assets", "No bank asset ranking is available for this selection.")

    top_banks = company_summary.nlargest(10, "bilan")
    figure = px.bar(
        top_banks,
        x="company",
        y="bilan",
        color="company",
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    figure.update_layout(showlegend=False)
    figure.update_xaxes(categoryorder="total descending", tickangle=-20)
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(
        figure,
        "Top Banks by Total Assets",
        x_title="Bank",
        y_title="Total Assets (FCFA)",
    )



def _build_company_bar_chart(
    company_summary: pd.DataFrame,
    metric_column: str,
    title: str,
    y_title: str,
) -> go.Figure:
    """Build a reusable company comparison bar chart.

    Purpose:
        Provide a single helper for repeated bank comparison visuals while
        keeping sorting, labels and styling consistent.

    Inputs:
        company_summary: Bank-level aggregated banking data.
        metric_column: Metric used on the y-axis.
        title: Chart title.
        y_title: Y-axis label.

    Outputs:
        A styled Plotly bar chart.
    """

    if company_summary.empty or metric_column not in company_summary.columns:
        return create_empty_figure(title, "No comparable bank data is available for this metric.")

    ordered = company_summary.sort_values(metric_column, ascending=False, kind="stable")
    figure = px.bar(
        ordered,
        x="company",
        y=metric_column,
        color="company",
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    figure.update_layout(showlegend=False)
    figure.update_xaxes(categoryorder="total descending", tickangle=-20)
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(figure, title, x_title="Bank", y_title=y_title)



def _build_profit_vs_assets_figure(company_year_summary: pd.DataFrame) -> go.Figure:
    """Build the profitability versus assets bubble chart.

    Purpose:
        Compare bank-year performance by relating balance sheet size, net result
        and net banking income within the filtered perimeter.

    Inputs:
        company_year_summary: Bank-year aggregated banking data.

    Outputs:
        A styled Plotly scatter chart.
    """

    required_columns = {"bilan", "resultat_net", "produit_net_bancaire"}
    if company_year_summary.empty or not required_columns.issubset(company_year_summary.columns):
        return create_empty_figure("Profit vs Assets", "No profit and asset data is available for this analysis.")

    scatter_frame = _ensure_size_column(company_year_summary, "produit_net_bancaire", "bubble_size")
    figure = px.scatter(
        scatter_frame,
        x="bilan",
        y="resultat_net",
        size="bubble_size",
        color="company",
        hover_name="company",
        hover_data={"year": True, "bilan": ":,.0f", "resultat_net": ":,.0f", "produit_net_bancaire": ":,.0f"},
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
        size_max=50,
    )
    figure.update_xaxes(tickformat=",")
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(
        figure,
        "Profit vs Assets",
        x_title="Total Assets (FCFA)",
        y_title="Resultat Net (FCFA)",
    )



def _build_profit_growth_figure(company_year_summary: pd.DataFrame) -> go.Figure:
    """Build the profit growth line chart.

    Purpose:
        Show how each bank's net result evolves across years for the active
        filter selection.

    Inputs:
        company_year_summary: Bank-year aggregated banking data.

    Outputs:
        A styled Plotly line chart.
    """

    if company_year_summary.empty or "resultat_net" not in company_year_summary.columns:
        return create_empty_figure("Profit Growth by Bank", "No historical profitability data is available.")

    figure = px.line(
        company_year_summary,
        x="year",
        y="resultat_net",
        color="company",
        markers=True,
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
        hover_data={"year": True, "resultat_net": ":,.0f", "company": True},
    )
    figure.update_traces(mode="lines+markers")
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(
        figure,
        "Profit Growth by Bank",
        x_title="Year",
        y_title="Resultat Net (FCFA)",
        hovermode="x unified",
    )



def _build_agency_vs_assets_figure(company_year_summary: pd.DataFrame) -> go.Figure:
    """Build the branch network versus assets scatter chart.

    Purpose:
        Relate operational footprint and asset scale while surfacing the net
        result as bubble size.

    Inputs:
        company_year_summary: Bank-year aggregated banking data.

    Outputs:
        A styled Plotly scatter chart.
    """

    required_columns = {"agence", "bilan", "resultat_net"}
    if company_year_summary.empty or not required_columns.issubset(company_year_summary.columns):
        return create_empty_figure("Agencies vs Assets", "No branch and asset data is available for this analysis.")

    scatter_frame = _ensure_size_column(company_year_summary, "resultat_net", "bubble_size")
    figure = px.scatter(
        scatter_frame,
        x="agence",
        y="bilan",
        size="bubble_size",
        color="company",
        hover_name="company",
        hover_data={"year": True, "agence": ":,.0f", "bilan": ":,.0f", "resultat_net": ":,.0f"},
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
        size_max=52,
    )
    figure.update_xaxes(tickformat=",")
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(
        figure,
        "Agencies vs Assets",
        x_title="Branches",
        y_title="Total Assets (FCFA)",
    )



def _build_workforce_vs_performance_figure(company_year_summary: pd.DataFrame) -> go.Figure:
    """Build the workforce versus performance scatter chart.

    Purpose:
        Compare staff size and net profitability for each bank-year point in the
        active filter selection.

    Inputs:
        company_year_summary: Bank-year aggregated banking data.

    Outputs:
        A styled Plotly scatter chart.
    """

    required_columns = {"effectif", "resultat_net"}
    if company_year_summary.empty or not required_columns.issubset(company_year_summary.columns):
        return create_empty_figure("Workforce vs Performance", "No workforce and performance data is available.")

    figure = px.scatter(
        company_year_summary,
        x="effectif",
        y="resultat_net",
        color="company",
        hover_name="company",
        hover_data={"year": True, "effectif": ":,.0f", "resultat_net": ":,.0f"},
        labels=BANKING_LABELS,
        template=PLOT_TEMPLATE,
        color_discrete_sequence=COLOR_SEQUENCE,
        size_max=44,
    )
    figure.update_xaxes(tickformat=",")
    figure.update_yaxes(tickformat=",")
    return _apply_chart_styling(
        figure,
        "Workforce vs Performance",
        x_title="Headcount",
        y_title="Resultat Net (FCFA)",
    )



def _build_ranking_table_data(company_summary: pd.DataFrame) -> list[dict[str, object]]:
    """Create the ranking table payload.

    Purpose:
        Build the top-bank table sorted by net result while keeping numeric
        values intact for DataTable sorting and formatting.

    Inputs:
        company_summary: Bank-level aggregated banking data.

    Outputs:
        A list of records ready for Dash DataTable.
    """

    ranking_columns = ["company", "bilan", "fonds_propres", "resultat_net", "produit_net_bancaire"]
    if company_summary.empty:
        return []

    ranking_frame = company_summary.copy()
    for column in ranking_columns:
        if column not in ranking_frame.columns:
            ranking_frame[column] = pd.NA

    ranking_frame = ranking_frame[ranking_columns].sort_values("resultat_net", ascending=False, kind="stable")
    ranking_frame = ranking_frame.reset_index(drop=True)
    return ranking_frame.to_dict("records")



def register_banking_callbacks(app: Dash, dataframe: pd.DataFrame) -> None:
    """Register callbacks for the advanced banking dashboard.

    Purpose:
        Connect the bank and year filters to dynamic KPIs, multi-tab charts and
        the interactive bank ranking table using a single in-memory DataFrame.

    Inputs:
        app: Dash application instance.
        dataframe: Banking DataFrame loaded once from MongoDB.

    Outputs:
        None. The function registers callbacks on the Dash app.
    """

    prepared_dataframe = _prepare_banking_dataframe(dataframe)

    @app.callback(
        Output("banking-year-filter", "options"),
        Output("banking-year-filter", "value"),
        Input("banking-bank-filter", "value"),
        State("banking-year-filter", "value"),
    )
    def update_banking_year_options(
        selected_bank: object,
        selected_year: object,
    ) -> tuple[list[dict[str, object]], object]:
        """Update available years according to the selected bank.

        Purpose:
            Keep the year dropdown focused on valid options for the chosen bank
            while preserving the current year when possible.

        Inputs:
            selected_bank: Current bank filter value.
            selected_year: Current year filter value.

        Outputs:
            A tuple containing the year dropdown options and the selected value.
        """

        filtered = prepared_dataframe
        if selected_bank not in (None, ALL_FILTER_VALUE) and "company" in prepared_dataframe.columns:
            filtered = prepared_dataframe[prepared_dataframe["company"] == selected_bank]

        options = build_dropdown_options(filtered.get("year", []), "All years")
        valid_values = {option["value"] for option in options}
        next_value = selected_year if selected_year in valid_values else ALL_FILTER_VALUE
        return options, next_value

    @app.callback(
        Output("banking-kpi-total-assets", "children"),
        Output("banking-kpi-total-funds", "children"),
        Output("banking-kpi-pnb", "children"),
        Output("banking-kpi-net-result", "children"),
        Output("banking-market-share-graph", "figure"),
        Output("banking-sector-evolution-graph", "figure"),
        Output("banking-top-banks-graph", "figure"),
        Output("banking-comparison-profit-graph", "figure"),
        Output("banking-comparison-funds-graph", "figure"),
        Output("banking-comparison-pnb-graph", "figure"),
        Output("banking-profit-vs-assets-graph", "figure"),
        Output("banking-profit-growth-graph", "figure"),
        Output("banking-agency-vs-assets-graph", "figure"),
        Output("banking-workforce-vs-performance-graph", "figure"),
        Output("banking-ranking-table", "data"),
        Input("banking-bank-filter", "value"),
        Input("banking-year-filter", "value"),
    )
    def update_banking_dashboard(
        selected_bank: object,
        selected_year: object,
    ) -> tuple[
        str,
        str,
        str,
        str,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        go.Figure,
        list[dict[str, object]],
    ]:
        """Update the full banking dashboard for the current filter state.

        Purpose:
            Recompute the dashboard's KPIs, analytical charts and ranking table
            from the preloaded banking DataFrame without requerying MongoDB.

        Inputs:
            selected_bank: Selected company filter value.
            selected_year: Selected year filter value.

        Outputs:
            A tuple containing KPI strings, Plotly figures and ranking table
            records for the banking dashboard.
        """

        filtered = filter_dataframe(prepared_dataframe, selected_bank, selected_year)
        company_summary = _aggregate_by_company(filtered)
        company_year_summary = _aggregate_by_company_and_year(filtered)

        total_assets = _format_kpi_metric(filtered, "bilan", snapshot_latest_year=True)
        total_funds = _format_kpi_metric(filtered, "fonds_propres", snapshot_latest_year=True)
        total_pnb = _format_kpi_metric(filtered, "produit_net_bancaire")
        total_net_result = _format_kpi_metric(filtered, "resultat_net")

        return (
            total_assets,
            total_funds,
            total_pnb,
            total_net_result,
            _build_market_share_figure(company_summary),
            _build_sector_evolution_figure(company_year_summary),
            _build_top_banks_figure(company_summary),
            _build_company_bar_chart(company_summary, "resultat_net", "Net Profit Comparison", "Resultat Net (FCFA)"),
            _build_company_bar_chart(company_summary, "fonds_propres", "Equity Comparison", "Fonds Propres (FCFA)"),
            _build_company_bar_chart(company_summary, "produit_net_bancaire", "PNB Comparison", "Produit Net Bancaire (FCFA)"),
            _build_profit_vs_assets_figure(company_year_summary),
            _build_profit_growth_figure(company_year_summary),
            _build_agency_vs_assets_figure(company_year_summary),
            _build_workforce_vs_performance_figure(company_year_summary),
            _build_ranking_table_data(company_summary),
        )

