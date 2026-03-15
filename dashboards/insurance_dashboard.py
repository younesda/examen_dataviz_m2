"""Premium multipage insurance dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html, dash_table
from dash.dash_table.Format import Format, Group, Scheme
from flask import Flask
from plotly.subplots import make_subplots

from dashboards.utils import ALL_FILTER_VALUE, build_dropdown_options, format_number

GOLD = "#C9A84C"
NAVY = "#0A1628"
GREEN = "#1A8A5A"
RED = "#D32F2F"
BLUE = "#1565C0"
PURPLE = "#6C3FC5"
ORANGE = "#E08A00"
TEXT = "#344256"
MUTED = "#73839A"
GRID = "rgba(148, 163, 184, 0.18)"
PRODUCT_COLORS = {"Auto": GOLD, "Habitation": BLUE, "Sant\u00e9": GREEN, "Vie": PURPLE, "RC Pro": ORANGE}
FALLBACK_PRODUCT_COLORS = ["#0EA5E9", "#F97316", "#14B8A6", "#F43F5E", "#8B5CF6", "#64748B"]

NAV_ITEMS = [
    {"key": "overview", "label": "Vue d'ensemble", "icon": "fa-gauge-high", "href": "/insurance/"},
    {"key": "portfolio", "label": "Portefeuille", "icon": "fa-briefcase", "href": "/insurance/portefeuille"},
    {"key": "claims", "label": "Risques", "icon": "fa-triangle-exclamation", "href": "/insurance/risques"},
    {"key": "finance", "label": "Finances", "icon": "fa-chart-line", "href": "/insurance/finances"},
]
PAGE_META = {
    "overview": ("Centre de commandement", "Vue d'ensemble", "Pilotage global du portefeuille, des volumes et de la pression sinistre."),
    "portfolio": ("Lecture portefeuille", "Portefeuille", "Lecture structurelle par branche, r\u00e9gion, sexe, \u00e2ge et dur\u00e9e de contrat."),
    "claims": ("Veille risque", "Risques", "Focus sur la fr\u00e9quence, la s\u00e9v\u00e9rit\u00e9 et les zones qui concentrent la sinistralit\u00e9."),
    "finance": ("Radar financier", "Finances", "Lecture technique du compte assurance, des marges et des segments sous pression."),
}
FMT_INT = Format(group=Group.yes, precision=0, scheme=Scheme.fixed)
FMT_DEC = Format(group=Group.yes, precision=2, scheme=Scheme.fixed)
FMT_PCT = Format(precision=2, scheme=Scheme.percentage)


def _title_case(value: object, fallback: str) -> str:
    if value is None or pd.isna(value):
        return fallback
    return str(value).strip().title() or fallback


def _product_label(value: object) -> str:
    raw = "" if value is None or pd.isna(value) else str(value).strip().lower()
    mapping = {
        "auto": "Auto",
        "habitation": "Habitation",
        "sante": "Sant\u00e9",
        "sant?": "Sant\u00e9",
        "vie": "Vie",
        "rc pro": "RC Pro",
        "rc_pro": "RC Pro",
        "rcpro": "RC Pro",
    }
    return mapping.get(raw, raw.title() if raw else "Portefeuille")


def _sex_label(value: object) -> str:
    raw = "" if value is None or pd.isna(value) else str(value).strip().lower()
    mapping = {"masculin": "Masculin", "homme": "Masculin", "male": "Masculin", "feminin": "F\u00e9minin", "f\u00e9minin": "F\u00e9minin", "female": "F\u00e9minin", "femme": "F\u00e9minin"}
    return mapping.get(raw, raw.title() if raw else "Non renseign\u00e9")


def _fmt(value: float | int | None, decimals: int = 0) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return format_number(value, decimals=decimals)


def _company_color_map(values: pd.Series | list[object]) -> dict[str, str]:
    color_map = dict(PRODUCT_COLORS)
    normalized_values = pd.Series(values, dtype="object").dropna().astype(str).unique().tolist()
    unknown_values = [value for value in normalized_values if value not in color_map]
    for index, value in enumerate(sorted(unknown_values)):
        color_map[value] = FALLBACK_PRODUCT_COLORS[index % len(FALLBACK_PRODUCT_COLORS)]
    return color_map


def _pct(value: float | int | None, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{decimals}%}"


def _style(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "DM Sans", "color": TEXT},
        margin={"l": 12, "r": 12, "t": 12, "b": 12},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        hoverlabel={"bgcolor": NAVY, "font": {"color": "#FFFFFF"}},
    )
    fig.update_xaxes(showgrid=False, zeroline=False, color=MUTED, tickfont={"size": 11})
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=MUTED, tickfont={"size": 11})
    return fig


def _empty(message: str, height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font={"size": 14, "color": MUTED})
    return _style(fig, height)


def _prepare_insurance_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    df = dataframe.copy()
    if "date_derniere_sinistre" in df.columns:
        df["date_derniere_sinistre"] = pd.to_datetime(df["date_derniere_sinistre"], errors="coerce")
    if "premiums" not in df.columns and "montant_prime" in df.columns:
        df["premiums"] = df["montant_prime"]
    if "claims" not in df.columns and "montant_sinistres" in df.columns:
        df["claims"] = df["montant_sinistres"]

    for column in ["premiums", "claims", "profit", "loss_ratio", "profit_margin", "age", "nb_sinistres", "duree_contrat", "year", "bonus_malus"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in ["premiums", "claims", "profit", "loss_ratio", "profit_margin", "age", "duree_contrat", "bonus_malus"]:
        if column not in df.columns:
            df[column] = pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")

    if "profit" not in dataframe.columns and {"premiums", "claims"}.issubset(df.columns):
        df["profit"] = df["premiums"] - df["claims"]
    if "loss_ratio" not in dataframe.columns and {"premiums", "claims"}.issubset(df.columns):
        df["loss_ratio"] = df["claims"].divide(df["premiums"].replace({0: pd.NA}))
    if "profit_margin" not in dataframe.columns and {"premiums", "profit"}.issubset(df.columns):
        df["profit_margin"] = df["profit"].divide(df["premiums"].replace({0: pd.NA}))

    if "year" not in df.columns and "date_derniere_sinistre" in df.columns:
        df["year"] = df["date_derniere_sinistre"].dt.year.astype("Int64")
    elif "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    else:
        df["year"] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Int64")

    if "company" not in df.columns:
        df["company"] = df["type_assurance"] if "type_assurance" in df.columns else "Portfolio"
    if "region" not in df.columns:
        df["region"] = "R\u00e9gion inconnue"
    if "sexe" not in df.columns:
        df["sexe"] = "Non renseign\u00e9"

    df["company"] = df["company"].map(_product_label)
    df["region"] = df["region"].map(lambda value: _title_case(value, "R\u00e9gion inconnue"))
    df["sexe"] = df["sexe"].map(_sex_label)

    claim_count_source = None
    if "nb_sinistres" in df.columns:
        claim_count_source = df["nb_sinistres"]
    elif "claim_count" in df.columns:
        claim_count_source = df["claim_count"]
    else:
        claim_count_source = pd.Series(0, index=df.index, dtype="float64")
    df["claim_count"] = pd.to_numeric(claim_count_source, errors="coerce").fillna(0)

    age_source = pd.to_numeric(df["age"], errors="coerce") if "age" in df.columns else pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")
    bonus_source = pd.to_numeric(df["bonus_malus"], errors="coerce") if "bonus_malus" in df.columns else pd.Series([float("nan")] * len(df), index=df.index, dtype="float64")
    df["age"] = age_source
    df["bonus_malus"] = bonus_source
    df["has_claim"] = df["claim_count"].gt(0)
    df["claim_severity"] = df["claims"].divide(df["claim_count"].replace({0: pd.NA}))
    df["female_flag"] = df["sexe"].eq("F\u00e9minin")
    df["age_band"] = pd.cut(age_source, bins=[17, 29, 39, 49, 59, 69, 120], labels=["18-29", "30-39", "40-49", "50-59", "60-69", "70+"])
    df["bonus_band"] = pd.cut(bonus_source, bins=[0, 0.8, 1.0, 1.2, 2.0], labels=["Bonus fort", "\u00c9quilibre", "Malus mod\u00e9r\u00e9", "Malus \u00e9lev\u00e9"])
    sort_cols = [c for c in ["year", "company", "region"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, kind="stable")
    return df.reset_index(drop=True)


def _filter_insurance_dataframe(dataframe: pd.DataFrame, company: object, year: object, region: object, sex: object = ALL_FILTER_VALUE) -> pd.DataFrame:
    df = dataframe.copy()
    if company not in (None, ALL_FILTER_VALUE) and "company" in df.columns:
        df = df[df["company"] == company]
    if year not in (None, ALL_FILTER_VALUE) and "year" in df.columns:
        df = df[df["year"] == year]
    if region not in (None, ALL_FILTER_VALUE) and "region" in df.columns:
        df = df[df["region"] == region]
    if sex not in (None, ALL_FILTER_VALUE) and "sexe" in df.columns:
        df = df[df["sexe"] == sex]
    return df


def _page_key(pathname: str | None) -> str:
    normalized = (pathname or "/insurance/").rstrip("/") or "/insurance"
    mapping = {"/insurance": "overview", "/insurance/portefeuille": "portfolio", "/insurance/risques": "claims", "/insurance/finances": "finance"}
    return mapping.get(normalized, "overview")


def _summary_by_company(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["company", "contracts", "regions", "premiums", "claims", "profit", "loss_ratio", "profit_margin", "claim_count", "claim_frequency", "claim_severity", "avg_age", "avg_duration", "bonus_malus", "female_share"])
    out = df.groupby("company", as_index=False).agg(
        contracts=("company", "size"), regions=("region", "nunique"), premiums=("premiums", "sum"), claims=("claims", "sum"), profit=("profit", "sum"),
        loss_ratio=("loss_ratio", "mean"), profit_margin=("profit_margin", "mean"), claim_count=("claim_count", "sum"), claim_frequency=("has_claim", "mean"),
        claim_severity=("claim_severity", "mean"), avg_age=("age", "mean"), avg_duration=("duree_contrat", "mean"), bonus_malus=("bonus_malus", "mean"), female_share=("female_flag", "mean"),
    )
    return out.sort_values("premiums", ascending=False, kind="stable").reset_index(drop=True)


def _summary_by_region(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["region", "contracts", "premiums", "claims", "profit", "loss_ratio", "claim_frequency", "claim_severity"])
    out = df.groupby("region", as_index=False).agg(contracts=("region", "size"), premiums=("premiums", "sum"), claims=("claims", "sum"), profit=("profit", "sum"), loss_ratio=("loss_ratio", "mean"), claim_frequency=("has_claim", "mean"), claim_severity=("claim_severity", "mean"))
    return out.sort_values("premiums", ascending=False, kind="stable").reset_index(drop=True)


def _summary_by_year(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "year" not in df.columns:
        return pd.DataFrame(columns=["year", "premiums", "claims", "profit", "contracts"])
    out = df.dropna(subset=["year"]).groupby("year", as_index=False).agg(premiums=("premiums", "sum"), claims=("claims", "sum"), profit=("profit", "sum"), contracts=("year", "size"))
    return out.sort_values("year", kind="stable").reset_index(drop=True)


def _summary_by_age_sex(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["age_band", "sexe", "contracts", "claim_frequency", "loss_ratio"])
    return df.dropna(subset=["age_band"]).groupby(["age_band", "sexe"], as_index=False, observed=True).agg(contracts=("company", "size"), claim_frequency=("has_claim", "mean"), loss_ratio=("loss_ratio", "mean")).reset_index(drop=True)


def _summary_by_bonus(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["bonus_band", "contracts", "claim_frequency", "loss_ratio"])
    return df.dropna(subset=["bonus_band"]).groupby("bonus_band", as_index=False, observed=True).agg(contracts=("company", "size"), claim_frequency=("has_claim", "mean"), loss_ratio=("loss_ratio", "mean")).reset_index(drop=True)


def _table(table_id: str, columns: list[dict[str, object]], data: list[dict[str, object]], page_size: int = 7) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=columns,
        data=data,
        page_action="native",
        page_size=page_size,
        sort_action="native",
        style_table={"overflowX": "auto", "width": "100%"},
        style_header={"backgroundColor": "#F7F8FC", "border": "none", "borderBottom": "1px solid rgba(15,23,42,0.08)", "color": MUTED, "fontSize": "11px", "fontWeight": "700", "letterSpacing": "0.12em", "padding": "12px 14px", "textTransform": "uppercase"},
        style_cell={"backgroundColor": "#FFFFFF", "border": "none", "borderBottom": "1px solid rgba(15,23,42,0.05)", "color": TEXT, "fontFamily": "DM Sans, sans-serif", "fontSize": "13px", "padding": "13px 14px", "textAlign": "left", "whiteSpace": "normal", "minWidth": "80px", "width": "80px", "maxWidth": "200px"},
        style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#FBFCFF"}],
    )


def _metric(label: str, value: str, helper: str, icon: str, tone: str) -> html.Div:
    return html.Div([html.Div(html.I(className=f"fa-solid {icon}"), className=f"insurance-metric-icon tone-{tone}"), html.Div(label, className="insurance-metric-label"), html.Div(value, className="insurance-metric-value"), html.Div(helper, className="insurance-metric-helper")], className="insurance-metric-card")


def _panel(title: str, subtitle: str, child: object, extra: str = "") -> dbc.Card:
    class_name = "insurance-panel-card"
    if extra:
        class_name = f"{class_name} {extra}"
    return dbc.Card(dbc.CardBody([html.Div(title, className="insurance-panel-title"), html.Div(subtitle, className="insurance-panel-subtitle"), child]), className=class_name)


def _graph(fig: go.Figure, extra_class: str = "", height: int = 300) -> dcc.Graph:
    class_name = "insurance-graph"
    if extra_class:
        class_name = f"{class_name} {extra_class}"
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "responsive": True}, className=class_name, style={"height": f"{height}px"})


def _safe_ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if pd.isna(numerator) or pd.isna(denominator):
        return None
    if float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)




def _claims_summary_by_company(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["company", "contracts", "claim_contracts", "claim_count", "claims", "premiums", "loss_ratio", "claim_frequency", "claim_severity", "share_of_total"])
    out = df.groupby("company", as_index=False).agg(
        contracts=("company", "size"),
        claim_contracts=("has_claim", "sum"),
        claim_count=("claim_count", "sum"),
        claims=("claims", "sum"),
        premiums=("premiums", "sum"),
    )
    out["loss_ratio"] = out["claims"].divide(out["premiums"].replace({0: pd.NA}))
    out["claim_frequency"] = out["claim_contracts"].divide(out["contracts"].replace({0: pd.NA}))
    out["claim_severity"] = out["claims"].divide(out["claim_count"].replace({0: pd.NA}))
    total_claims = out["claims"].sum()
    out["share_of_total"] = out["claims"].divide(total_claims if total_claims else pd.NA)
    return out.sort_values(["claims", "claim_count"], ascending=[False, False], kind="stable").reset_index(drop=True)



def _claims_summary_by_bonus(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["bonus_band", "contracts", "claim_contracts", "claim_count", "claims", "premiums", "loss_ratio", "claim_frequency"])
    out = df.dropna(subset=["bonus_band"]).groupby("bonus_band", as_index=False, observed=True).agg(
        contracts=("company", "size"),
        claim_contracts=("has_claim", "sum"),
        claim_count=("claim_count", "sum"),
        claims=("claims", "sum"),
        premiums=("premiums", "sum"),
    )
    out["loss_ratio"] = out["claims"].divide(out["premiums"].replace({0: pd.NA}))
    out["claim_frequency"] = out["claim_contracts"].divide(out["contracts"].replace({0: pd.NA}))
    return out.sort_values(["loss_ratio", "claim_frequency"], ascending=[False, False], kind="stable").reset_index(drop=True)



def _fig_overview_trend(df: pd.DataFrame) -> go.Figure:
    yearly = _summary_by_year(df)
    if yearly.empty:
        return _empty("Aucune lecture annuelle disponible.", 300)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=yearly["year"], y=yearly["premiums"], name="Primes", marker_color=GOLD), secondary_y=False)
    fig.add_trace(go.Bar(x=yearly["year"], y=yearly["claims"], name="Sinistres", marker_color=RED), secondary_y=False)
    fig.add_trace(go.Scatter(x=yearly["year"], y=yearly["profit"], name="R\u00e9sultat", mode="lines+markers", line={"width": 3, "color": GREEN}, marker={"size": 7}), secondary_y=True)
    fig.update_layout(barmode="group")
    fig.update_yaxes(showgrid=False, secondary_y=True)
    return _style(fig, 300)


def _fig_overview_mix(df: pd.DataFrame) -> go.Figure:
    summary = _summary_by_company(df)
    if summary.empty:
        return _empty("Aucune r\u00e9partition disponible.", 300)
    color_map = _company_color_map(summary["company"])
    fig = go.Figure(go.Pie(labels=summary["company"], values=summary["premiums"], hole=0.68, marker={"colors": [color_map.get(v, BLUE) for v in summary["company"]], "line": {"color": "white", "width": 3}}, textinfo="none"))
    fig.update_layout(annotations=[{"text": f"<b>{_fmt(summary['premiums'].sum(), 1)}</b><br><span style='font-size:11px;color:{MUTED}'>primes</span>", "x": 0.5, "y": 0.5, "showarrow": False, "font": {"family": "Syne", "size": 16, "color": NAVY}}])
    return _style(fig, 300)


def _fig_region_pressure(df: pd.DataFrame) -> go.Figure:
    summary = _summary_by_region(df)
    if summary.empty:
        return _empty("Aucune pression r\u00e9gionale disponible.", 300)
    colors = [GREEN if value < 1 else ORANGE if value < 2 else RED for value in summary["loss_ratio"].fillna(0)]
    fig = go.Figure(go.Bar(x=summary["loss_ratio"], y=summary["region"], orientation="h", marker={"color": colors, "cornerradius": 8}, text=[_pct(v, 0) for v in summary["loss_ratio"]], textposition="outside"))
    fig.update_xaxes(tickformat=".0%")
    return _style(fig, 300)


def _fig_portfolio_volume(df: pd.DataFrame) -> go.Figure:
    summary = _summary_by_company(df)
    if summary.empty:
        return _empty("Aucun volume par branche disponible.")
    color_map = _company_color_map(summary["company"])
    fig = go.Figure(go.Bar(x=summary["contracts"], y=summary["company"], orientation="h", marker={"color": [color_map.get(v, BLUE) for v in summary["company"]], "cornerradius": 8}, text=summary["contracts"], textposition="outside"))
    return _style(fig)


def _fig_portfolio_heatmap(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return _empty("Aucune intensit\u00e9 r\u00e9gionale disponible.")
    pivot = df.pivot_table(index="region", columns="company", values="premiums", aggfunc="sum", fill_value=0)
    if pivot.empty:
        return _empty("Aucune intensit\u00e9 r\u00e9gionale disponible.")
    fig = go.Figure(go.Heatmap(z=pivot.values, x=list(pivot.columns), y=list(pivot.index), colorscale=[[0, "#EEF3FF"], [0.5, "#A7C0F5"], [1, BLUE]], colorbar={"title": "Primes"}))
    return _style(fig)


def _fig_portfolio_age(df: pd.DataFrame) -> go.Figure:
    if df.empty or "age" not in df.columns:
        return _empty("Aucune lecture d\'\u00e2ge disponible.")
    fig = px.box(df, x="company", y="age", color="sexe", color_discrete_map={"Masculin": BLUE, "F\u00e9minin": PURPLE, "Non renseign\u00e9": MUTED}, points=False)
    return _style(fig)


def _fig_claims_branch(df: pd.DataFrame) -> go.Figure:
    summary = _claims_summary_by_company(df)
    if summary.empty:
        return _empty("Aucune charge sinistre disponible.", 360)

    customdata = summary[["share_of_total", "loss_ratio", "claim_severity", "claim_contracts", "claim_frequency", "claim_count"]].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=summary["company"],
            y=summary["claim_count"],
            name="Nb sinistres",
            marker={"color": GOLD, "cornerradius": 10},
            customdata=customdata,
            hovertemplate="<b>%{x}</b><br>Nb sinistres: %{y:,.0f}<br>Contrats sinistres: %{customdata[3]:,.0f}<br>Frequence: %{customdata[4]:.1%}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=summary["company"],
            y=summary["claim_contracts"],
            name="Contrats sinistres",
            marker={"color": BLUE, "cornerradius": 10},
            customdata=customdata,
            hovertemplate="<b>%{x}</b><br>Contrats sinistres: %{y:,.0f}<br>Nb sinistres: %{customdata[5]:,.0f}<br>Part de charge: %{customdata[0]:.1%}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=summary["company"],
            y=summary["claims"],
            name="Montant des sinistres",
            mode="lines+markers+text",
            text=[_pct(value) for value in summary["share_of_total"]],
            textposition="top center",
            line={"width": 3.5, "color": RED, "shape": "spline", "smoothing": 1.05},
            marker={"size": 8, "color": RED, "line": {"width": 2, "color": "#ffffff"}},
            customdata=customdata,
            hovertemplate="<b>%{x}</b><br>Montant: %{y:,.1f}<br>Part du total: %{customdata[0]:.1%}<br>Loss ratio: %{customdata[1]:.1%}<br>Severite moyenne: %{customdata[2]:,.1f}<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        barmode="group",
        bargap=0.24,
        bargroupgap=0.1,
        margin={"l": 16, "r": 22, "t": 14, "b": 8},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    fig.update_xaxes(showgrid=False, tickfont={"size": 11})
    fig.update_yaxes(title_text="Sinistres / contrats", rangemode="tozero", gridcolor="rgba(148, 163, 184, 0.12)", secondary_y=False)
    fig.update_yaxes(title_text="Montant des sinistres", rangemode="tozero", tickformat="~s", showgrid=False, secondary_y=True)
    return _style(fig, 300)


def _fig_claims_demography(df: pd.DataFrame) -> go.Figure:
    summary = _summary_by_age_sex(df)
    if summary.empty:
        return _empty("Aucune d\u00e9mographie de risque disponible.", 300)
    fig = px.bar(summary, x="age_band", y="claim_frequency", color="sexe", barmode="group", color_discrete_map={"Masculin": BLUE, "F\u00e9minin": PURPLE, "Non renseign\u00e9": MUTED})
    fig.update_yaxes(tickformat=".0%")
    return _style(fig, 300)


def _fig_bonus_pressure(df: pd.DataFrame) -> go.Figure:
    summary = _claims_summary_by_bonus(df)
    if summary.empty:
        return _empty("Aucune lecture bonus-malus disponible.", 300)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=summary["bonus_band"], y=summary["claim_frequency"], name="Fr\u00e9quence", marker_color=GOLD), secondary_y=False)
    fig.add_trace(go.Scatter(x=summary["bonus_band"], y=summary["loss_ratio"], name="Loss ratio", mode="lines+markers", line={"width": 3, "color": RED}, marker={"size": 7}), secondary_y=True)
    fig.update_yaxes(tickformat=".0%", secondary_y=False)
    fig.update_yaxes(tickformat=".0%", secondary_y=True, showgrid=False)
    return _style(fig, 300)


def _fig_finance_trend(df: pd.DataFrame) -> go.Figure:
    return _fig_overview_trend(df)


def _fig_finance_scatter(df: pd.DataFrame) -> go.Figure:
    summary = _summary_by_company(df)
    if summary.empty:
        return _empty("Aucune lecture marge / risque disponible.", 300)
    fig = px.scatter(summary, x="loss_ratio", y="profit_margin", size="premiums", color="claim_frequency", text="company", color_continuous_scale=[[0, "#DDE9FF"], [0.5, GOLD], [1, RED]])
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(tickformat=".0%")
    fig.update_traces(textposition="top center", marker={"line": {"width": 1, "color": "rgba(15,23,42,0.2)"}})
    return _style(fig, 300)


def _fig_finance_region(df: pd.DataFrame) -> go.Figure:
    summary = _summary_by_region(df)
    if summary.empty:
        return _empty("Aucune contribution r\u00e9gionale disponible.", 300)
    colors = [GREEN if value >= 0 else RED for value in summary["profit"].fillna(0)]
    fig = go.Figure(go.Bar(x=summary["region"], y=summary["profit"], marker={"color": colors, "cornerradius": 8}))
    return _style(fig, 300)

def _overview_hero(df: pd.DataFrame) -> html.Div:
    n_branches = df["company"].nunique() if "company" in df.columns and not df.empty else 0
    n_regions = df["region"].nunique() if "region" in df.columns and not df.empty else 0
    loss = df["loss_ratio"].mean() if "loss_ratio" in df.columns and not df.empty else None
    primes = df["premiums"].sum() if "premiums" in df.columns and not df.empty else None
    return html.Div([
        html.Div([
            html.Div("Centre de commandement", className="insurance-overview-kicker"),
            html.Div("Vue d\u2019ensemble du portefeuille", className="insurance-overview-hero-title"),
            html.P(
                "Pilotage global sur le p\u00e9rim\u00e8tre visible apr\u00e8s filtres \u2013 primes, sinistres et pression technique consolid\u00e9s.",
                className="insurance-overview-hero-copy",
            ),
        ], className="insurance-overview-hero-left"),
        html.Div([
            html.Div([
                html.Div(_fmt(primes, 1), className="insurance-overview-stat-value"),
                html.Div("primes brutes", className="insurance-overview-stat-label"),
            ], className="insurance-overview-stat"),
            html.Div(className="insurance-overview-stat-sep"),
            html.Div([
                html.Div(_pct(loss), className="insurance-overview-stat-value"),
                html.Div("loss ratio", className="insurance-overview-stat-label"),
            ], className="insurance-overview-stat"),
            html.Div(className="insurance-overview-stat-sep"),
            html.Div([
                html.Div(_fmt(n_branches), className="insurance-overview-stat-value"),
                html.Div("branches", className="insurance-overview-stat-label"),
            ], className="insurance-overview-stat"),
            html.Div(className="insurance-overview-stat-sep"),
            html.Div([
                html.Div(_fmt(n_regions), className="insurance-overview-stat-value"),
                html.Div("r\u00e9gions", className="insurance-overview-stat-label"),
            ], className="insurance-overview-stat"),
        ], className="insurance-overview-hero-right"),
    ], className="insurance-overview-hero")


def _overview_page(df: pd.DataFrame) -> html.Div:
    summary = _summary_by_company(df)
    summary_table = _table("insurance-overview-table", [
        {"name": "Branche", "id": "company"},
        {"name": "Contrats", "id": "contracts", "type": "numeric", "format": FMT_INT},
        {"name": "R\u00e9gions", "id": "regions", "type": "numeric", "format": FMT_INT},
        {"name": "Primes", "id": "premiums", "type": "numeric", "format": FMT_DEC},
        {"name": "Sinistres", "id": "claims", "type": "numeric", "format": FMT_DEC},
        {"name": "R\u00e9sultat", "id": "profit", "type": "numeric", "format": FMT_DEC},
        {"name": "Loss ratio", "id": "loss_ratio", "type": "numeric", "format": FMT_PCT},
    ], summary.round(4).to_dict("records"), 6)
    return html.Div([
        _overview_hero(df),
        html.Div([
            _metric("Contrats", _fmt(len(df)), "Volume visible apr\u00e8s filtres", "fa-file-contract", "gold"),
            _metric("Primes", _fmt(df["premiums"].sum() if "premiums" in df else None, 1), "Production brute cumul\u00e9e", "fa-sack-dollar", "blue"),
            _metric("Sinistres", _fmt(df["claims"].sum() if "claims" in df else None, 1), "Charge cumul\u00e9e visible", "fa-car-burst", "red"),
            _metric("Loss ratio", _pct(df["loss_ratio"].mean() if "loss_ratio" in df and not df.empty else None), "Pression moyenne du portefeuille", "fa-scale-unbalanced", "green"),
        ], className="insurance-metric-grid"),
        dbc.Row([dbc.Col(_panel("Trajectoire technique", "Primes, sinistres et r\u00e9sultat par ann\u00e9e", _graph(_fig_overview_trend(df))), lg=8), dbc.Col(_panel("Mix portefeuille", "Poids des branches dans les primes visibles", _graph(_fig_overview_mix(df))), lg=4)], className="g-3"),
        dbc.Row([dbc.Col(_panel("Pression r\u00e9gionale", "Loss ratio moyen par r\u00e9gion", _graph(_fig_region_pressure(df))), lg=12)], className="g-3"),
        _panel("Synth\u00e8se executive", "Comparaison rapide des branches actives", summary_table, "insurance-table-card"),
    ], className="insurance-page-stack insurance-page-animate")


def _portfolio_page(df: pd.DataFrame) -> html.Div:
    summary = _summary_by_company(df)
    portfolio_table = _table("insurance-portfolio-table", [
        {"name": "Branche", "id": "company"},
        {"name": "Contrats", "id": "contracts", "type": "numeric", "format": FMT_INT},
        {"name": "Age moyen", "id": "avg_age", "type": "numeric", "format": FMT_DEC},
        {"name": "Dur\u00e9e moyenne", "id": "avg_duration", "type": "numeric", "format": FMT_DEC},
        {"name": "Bonus-malus", "id": "bonus_malus", "type": "numeric", "format": FMT_DEC},
        {"name": "Part femmes", "id": "female_share", "type": "numeric", "format": FMT_PCT},
    ], summary.round(4).to_dict("records"), 6)
    return html.Div([
        html.Div([
            _metric("Branches", _fmt(df["company"].nunique() if "company" in df and not df.empty else 0), "Nombre de lignes visibles", "fa-layer-group", "gold"),
            _metric("R\u00e9gions", _fmt(df["region"].nunique() if "region" in df and not df.empty else 0), "Zones couvertes par le scope actif", "fa-map-location-dot", "blue"),
            _metric("Prime moyenne", _fmt(df["premiums"].mean() if "premiums" in df and not df.empty else None, 1), "Valeur moyenne par contrat", "fa-hand-holding-dollar", "green"),
            _metric("Dur\u00e9e moyenne", _fmt(df["duree_contrat"].mean() if "duree_contrat" in df and not df.empty else None, 1), "Anciennet\u00e9 moyenne du portefeuille", "fa-clock-rotate-left", "purple"),
        ], className="insurance-metric-grid"),
        dbc.Row([dbc.Col(_panel("Volume par branche", "Nombre de contrats et poids relatif", _graph(_fig_portfolio_volume(df))), lg=5), dbc.Col(_panel("Intensit\u00e9 r\u00e9gionale", "Primes cumul\u00e9es par r\u00e9gion et branche", _graph(_fig_portfolio_heatmap(df))), lg=7)], className="g-3"),
        dbc.Row([dbc.Col(_panel("Dispersion d\'\u00e2ge", "Amplitude d\u00e9mographique du portefeuille", _graph(_fig_portfolio_age(df))), lg=12)], className="g-3"),
        _panel("Structure par branche", "Lecture d\u00e9taill\u00e9e des attributs du portefeuille", portfolio_table, "insurance-table-card"),
    ], className="insurance-page-stack insurance-page-animate")



def _claims_page(df: pd.DataFrame) -> html.Div:
    focus = df[df["has_claim"]].copy() if "has_claim" in df.columns and not df.empty else df.iloc[0:0].copy()
    claim_contracts = len(focus)
    total_claims = focus["claim_count"].sum() if "claim_count" in focus.columns and not focus.empty else 0
    total_claim_amount = df["claims"].sum() if "claims" in df.columns and not df.empty else None
    total_premiums = df["premiums"].sum() if "premiums" in df.columns and not df.empty else None
    severity = _safe_ratio(total_claim_amount, total_claims)
    loss_ratio = _safe_ratio(total_claim_amount, total_premiums)
    freq = df["has_claim"].mean() if "has_claim" in df.columns and not df.empty else None
    risk_summary = _summary_by_company(df)
    risk_table = _table(
        "insurance-risk-table",
        [
            {"name": "Branche", "id": "company"},
            {"name": "Contrats sinistr\u00e9s", "id": "claim_count", "type": "numeric", "format": FMT_INT},
            {"name": "Fr\u00e9quence", "id": "claim_frequency", "type": "numeric", "format": FMT_PCT},
            {"name": "S\u00e9v\u00e9rit\u00e9 moy.", "id": "claim_severity", "type": "numeric", "format": FMT_DEC},
            {"name": "Charge totale", "id": "claims", "type": "numeric", "format": FMT_DEC},
            {"name": "Loss ratio", "id": "loss_ratio", "type": "numeric", "format": FMT_PCT},
        ],
        risk_summary.round(4).to_dict("records"),
        6,
    )
    return html.Div([
        html.Div([
            _metric("Contrats sinistr\u00e9s", _fmt(claim_contracts), f"{_pct(freq)} du portefeuille touch\u00e9", "fa-file-circle-exclamation", "red"),
            _metric("Sinistres d\u00e9clar\u00e9s", _fmt(total_claims), f"{_fmt(_safe_ratio(total_claims, claim_contracts), 1)} sinistres par contrat", "fa-burst", "gold"),
            _metric("S\u00e9v\u00e9rit\u00e9 moyenne", _fmt(severity, 1), f"{_fmt(total_claim_amount, 1)} de charge totale", "fa-fire-flame-curved", "purple"),
            _metric("Loss ratio", _pct(loss_ratio), f"{_fmt(total_claim_amount, 1)} pour {_fmt(total_premiums, 1)} de primes", "fa-scale-unbalanced", "blue"),
        ], className="insurance-metric-grid"),
        dbc.Row([dbc.Col(_panel("Charge par branche", "Volumes et montants de sinistres par branche", _graph(_fig_claims_branch(df))), lg=7), dbc.Col(_panel("Fr\u00e9quence par \u00e2ge", "Fr\u00e9quence de sinistres selon l'\u00e2ge et le sexe", _graph(_fig_claims_demography(df))), lg=5)], className="g-3"),
        dbc.Row([dbc.Col(_panel("Signal bonus-malus", "Fr\u00e9quence et loss ratio selon le niveau bonus-malus", _graph(_fig_bonus_pressure(df))), lg=12)], className="g-3"),
        _panel("Synth\u00e8se risque par branche", "Indicateurs de sinistralit\u00e9 agr\u00e9g\u00e9s par ligne de produit", risk_table, "insurance-table-card"),
    ], className="insurance-page-stack insurance-page-animate")


def _finance_page(df: pd.DataFrame) -> html.Div:
    summary_company = _summary_by_company(df)
    summary_region = _summary_by_region(df)
    best_branch = summary_company.sort_values("profit", ascending=False, kind="stable").head(1)
    worst_region = summary_region.sort_values("profit", ascending=True, kind="stable").head(1)
    finance_table = _table("insurance-finance-table", [
        {"name": "Branche", "id": "company"},
        {"name": "Contrats", "id": "contracts", "type": "numeric", "format": FMT_INT},
        {"name": "Primes", "id": "premiums", "type": "numeric", "format": FMT_DEC},
        {"name": "Sinistres", "id": "claims", "type": "numeric", "format": FMT_DEC},
        {"name": "R\u00e9sultat", "id": "profit", "type": "numeric", "format": FMT_DEC},
        {"name": "Loss ratio", "id": "loss_ratio", "type": "numeric", "format": FMT_PCT},
        {"name": "Marge", "id": "profit_margin", "type": "numeric", "format": FMT_PCT},
    ], summary_company.round(4).to_dict("records"), 6)
    return html.Div([
        html.Div([
            _metric("R\u00e9sultat", _fmt(df["profit"].sum() if "profit" in df and not df.empty else None, 1), "Primes moins charge sinistre", "fa-square-poll-vertical", "green"),
            _metric("Marge moyenne", _pct(df["profit_margin"].mean() if "profit_margin" in df and not df.empty else None), "Signal moyen de rentabilit\u00e9", "fa-percent", "gold"),
            _metric("Branche leader", best_branch.iloc[0]["company"] if not best_branch.empty else "N/A", _fmt(best_branch.iloc[0]["profit"], 1) if not best_branch.empty else "Pas de leader", "fa-trophy", "blue"),
            _metric("R\u00e9gion sous pression", worst_region.iloc[0]["region"] if not worst_region.empty else "N/A", _fmt(worst_region.iloc[0]["profit"], 1) if not worst_region.empty else "Pas de faiblesse marqu\u00e9e", "fa-circle-exclamation", "red"),
        ], className="insurance-metric-grid"),
        dbc.Row([dbc.Col(_panel("Compte technique", "Trajectoire annuelle des primes, sinistres et r\u00e9sultat", _graph(_fig_finance_trend(df))), lg=7), dbc.Col(_panel("Marge vs risque", "Positionnement des branches selon pression et rentabilit\u00e9", _graph(_fig_finance_scatter(df))), lg=5)], className="g-3"),
        dbc.Row([dbc.Col(_panel("Contribution r\u00e9gionale", "Profit cumul\u00e9 par r\u00e9gion visible", _graph(_fig_finance_region(df))), lg=12)], className="g-3"),
        _panel("Synth\u00e8se financi\u00e8re", "Vue compar\u00e9e des branches sur les indicateurs cl\u00e9s", finance_table, "insurance-table-card"),
    ], className="insurance-page-stack insurance-page-animate")


PAGE_BUILDERS = {"overview": _overview_page, "portfolio": _portfolio_page, "claims": _claims_page, "finance": _finance_page}

def _selection_badges(df: pd.DataFrame, company: object, year: object, region: object, sex: object) -> list[html.Span]:
    return [
        html.Span(f"{_fmt(len(df))} contrats", className="insurance-topbar-badge insurance-topbar-badge-strong"),
        html.Span(f"Branche: {company if company not in (None, ALL_FILTER_VALUE) else 'Toutes'}", className="insurance-topbar-badge"),
        html.Span(f"Ann\u00e9e: {year if year not in (None, ALL_FILTER_VALUE) else 'Toutes'}", className="insurance-topbar-badge"),
        html.Span(f"R\u00e9gion: {region if region not in (None, ALL_FILTER_VALUE) else 'Toutes'}", className="insurance-topbar-badge"),
        html.Span(f"Sexe: {sex if sex not in (None, ALL_FILTER_VALUE) else 'Tous'}", className="insurance-topbar-badge"),
    ]


def _sidebar(prepared: pd.DataFrame, error_message: str | None = None) -> html.Div:
    company_options = build_dropdown_options(prepared.get("company", []), "Toutes les branches")
    year_options = build_dropdown_options(prepared.get("year", []), "Toutes les ann\u00e9es")
    region_options = build_dropdown_options(prepared.get("region", []), "Toutes les r\u00e9gions")
    sex_options = build_dropdown_options(prepared.get("sexe", []), "Tous les profils")
    window = "Fen\u00eatre indisponible"
    if not prepared.empty and "year" in prepared.columns and prepared["year"].dropna().any():
        window = f"{int(prepared['year'].dropna().min())} - {int(prepared['year'].dropna().max())}"
    status = error_message or "Dashboard multipages reconstruit dans un style ex\u00e9cutif, avec filtres partag\u00e9s et vues sp\u00e9cialis\u00e9es."
    return html.Div([
        html.Div([html.Div(html.I(className="fa-solid fa-umbrella"), className="insurance-brand-logo"), html.Div([html.Div([html.Span("Assur", className="insurance-brand-accent"), html.Span("Prime", className="insurance-brand-main")]), html.Div("Suite assurance ex\u00e9cutive", className="insurance-brand-subtitle")])], className="insurance-brand"),
        html.Div([html.Div("Navigation", className="insurance-rail-label"), html.Div([dcc.Link([html.I(className=f"fa-solid {item['icon']} insurance-nav-icon"), html.Span(item["label"], className="insurance-nav-text")], href=item["href"], className="insurance-nav-link", id=f"insurance-nav-{item['key']}", refresh=False) for item in NAV_ITEMS], className="insurance-nav-list")], className="insurance-sidebar-card"),
        html.Div([
            html.Div("Filtres partag\u00e9s", className="insurance-rail-label"),
            html.Div([html.Label("Branche", className="insurance-filter-label"), dcc.Dropdown(id="insurance-company-filter", options=company_options, value=ALL_FILTER_VALUE, clearable=False, className="insurance-select")], className="insurance-filter-block"),
            html.Div([html.Label("Ann\u00e9e", className="insurance-filter-label"), dcc.Dropdown(id="insurance-year-filter", options=year_options, value=ALL_FILTER_VALUE, clearable=False, className="insurance-select")], className="insurance-filter-block"),
            html.Div([html.Label("R\u00e9gion", className="insurance-filter-label"), dcc.Dropdown(id="insurance-region-filter", options=region_options, value=ALL_FILTER_VALUE, clearable=False, className="insurance-select")], className="insurance-filter-block"),
            html.Div([html.Label("Sexe", className="insurance-filter-label"), dcc.Dropdown(id="insurance-sex-filter", options=sex_options, value=ALL_FILTER_VALUE, clearable=False, className="insurance-select")], className="insurance-filter-block"),
        ], className="insurance-sidebar-card insurance-filter-rail"),
        html.Div([
            html.Div("Radar dataset", className="insurance-rail-label"),
            html.Div([html.Div(_fmt(len(prepared)), className="insurance-side-stat-value"), html.Div("contrats charg\u00e9s", className="insurance-side-stat-label")], className="insurance-side-stat"),
            html.Div([html.Div(_fmt(prepared["company"].nunique() if "company" in prepared.columns and not prepared.empty else 0), className="insurance-side-stat-value"), html.Div("branches suivies", className="insurance-side-stat-label")], className="insurance-side-stat"),
            html.Div([html.Div(_fmt(prepared["region"].nunique() if "region" in prepared.columns and not prepared.empty else 0), className="insurance-side-stat-value"), html.Div("r\u00e9gions visibles", className="insurance-side-stat-label")], className="insurance-side-stat"),
            html.Div([html.Div(window, className="insurance-side-stat-value"), html.Div("fen\u00eatre temporelle", className="insurance-side-stat-label")], className="insurance-side-stat"),
            html.Div(status, className="insurance-sidebar-note"),
        ], className="insurance-sidebar-card insurance-sidebar-summary"),
        html.Div([
            html.Div("Exporter les donn\u00e9es", className="insurance-rail-label"),
            html.Button([html.I(className="fa-solid fa-file-csv"), html.Span("\u00a0 T\u00e9l\u00e9charger CSV")], id="insurance-export-csv", className="insurance-export-btn", n_clicks=0, style={"width": "100%", "marginBottom": "8px"}),
            html.Button([html.I(className="fa-solid fa-file-excel"), html.Span("\u00a0 T\u00e9l\u00e9charger Excel")], id="insurance-export-excel", className="insurance-export-btn insurance-export-btn--excel", n_clicks=0, style={"width": "100%"}),
        ], className="insurance-sidebar-card"),
    ], className="insurance-suite-sidebar")


def create_insurance_layout(dataframe: pd.DataFrame, error_message: str | None = None) -> html.Div:
    prepared = _prepare_insurance_dataframe(dataframe)
    return html.Div([
        dcc.Location(id="insurance-location", refresh=False),
        dcc.Download(id="insurance-download"),
        html.Div([
            _sidebar(prepared, error_message),
            html.Div([
                html.Div([
                    html.Div([html.Div(id="insurance-page-eyebrow", className="insurance-topbar-eyebrow"), html.H1(id="insurance-page-title", className="insurance-topbar-title"), html.P(id="insurance-page-subtitle", className="insurance-topbar-subtitle")]),
                    html.Div([
                        html.Div([
                            html.A([html.I(className="fa-solid fa-arrow-left"), html.Span("Retour accueil")], href="/", className="insurance-home-link"),
                            html.Div(datetime.now().strftime("%d/%m/%Y"), className="insurance-topbar-date"),
                        ], className="insurance-topbar-meta"),
                        html.Div(id="insurance-selection-badges", className="insurance-topbar-badges"),
                    ], className="insurance-topbar-side"),
                ], className="insurance-topbar"),
                html.Div(id="insurance-page-body", className="insurance-suite-content"),
            ], className="insurance-suite-main"),
        ], className="insurance-suite-shell"),
    ], className="insurance-suite")


def register_insurance_callbacks(app: Dash, dataframe_provider: Callable[[], pd.DataFrame]) -> None:
    @app.callback(
        Output("insurance-page-eyebrow", "children"),
        Output("insurance-page-title", "children"),
        Output("insurance-page-subtitle", "children"),
        Output("insurance-selection-badges", "children"),
        Output("insurance-page-body", "children"),
        *[Output(f"insurance-nav-{item['key']}", "className") for item in NAV_ITEMS],
        Input("insurance-location", "pathname"),
        Input("insurance-company-filter", "value"),
        Input("insurance-year-filter", "value"),
        Input("insurance-region-filter", "value"),
        Input("insurance-sex-filter", "value"),
    )
    def render(pathname: str | None, company: object, year: object, region: object, sex: object) -> tuple[object, ...]:
        prepared = _prepare_insurance_dataframe(dataframe_provider())
        filtered = _filter_insurance_dataframe(prepared, company, year, region, sex)
        key = _page_key(pathname)
        eyebrow, title, subtitle = PAGE_META[key]
        body = PAGE_BUILDERS[key](filtered)
        badges = _selection_badges(filtered, company, year, region, sex)
        nav_classes = ["insurance-nav-link is-active" if item["key"] == key else "insurance-nav-link" for item in NAV_ITEMS]
        return eyebrow, title, subtitle, badges, body, *nav_classes

    @app.callback(
        Output("insurance-download", "data"),
        Input("insurance-export-csv", "n_clicks"),
        Input("insurance-export-excel", "n_clicks"),
        State("insurance-company-filter", "value"),
        State("insurance-year-filter", "value"),
        State("insurance-region-filter", "value"),
        State("insurance-sex-filter", "value"),
        prevent_initial_call=True,
    )
    def export_data(csv_clicks: int, excel_clicks: int, company: object, year: object, region: object, sex: object) -> object:
        from dash import ctx
        prepared = _prepare_insurance_dataframe(dataframe_provider())
        filtered = _filter_insurance_dataframe(prepared, company, year, region, sex)
        export_cols = [c for c in [
            "company", "region", "sex", "age", "contract_duration",
            "premiums", "claims", "claim_count", "has_claim",
            "claim_frequency", "claim_severity", "loss_ratio",
        ] if c in filtered.columns]
        df_export = filtered[export_cols].copy()
        suffix = ""
        if company and company != ALL_FILTER_VALUE:
            suffix += f"_{str(company)}"
        if year and year != ALL_FILTER_VALUE:
            suffix += f"_{str(year)}"
        if ctx.triggered_id == "insurance-export-excel":
            return dcc.send_data_frame(df_export.to_excel, f"insurance_portfolio{suffix}.xlsx", sheet_name="Portefeuille", index=False)
        return dcc.send_data_frame(df_export.to_csv, f"insurance_portfolio{suffix}.csv", sep=";", index=False, encoding="utf-8-sig")


def create_insurance_dashboard(
    server: Flask,
    callback_dataframe_provider: Callable[[], pd.DataFrame],
    error_provider: Callable[[], str | None] | None = None,
    layout_dataframe_provider: Callable[[], pd.DataFrame] | None = None,
) -> Dash:
    dash_app = Dash(
        name="insurance_dashboard",
        server=server,
        url_base_pathname="/insurance/",
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            "https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:wght@300;400;500;600;700&display=swap",
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css",
        ],
        suppress_callback_exceptions=True,
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
        title="AssurPrime Dashboard",
    )
    layout_dataframe_provider = layout_dataframe_provider or callback_dataframe_provider
    dash_app.layout = lambda: create_insurance_layout(layout_dataframe_provider(), error_provider() if error_provider is not None else None)
    register_insurance_callbacks(dash_app, callback_dataframe_provider)
    return dash_app










