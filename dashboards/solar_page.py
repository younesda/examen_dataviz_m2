"""Solar Observatory page rendered directly from the official HTML/CSS/JS template."""

from __future__ import annotations

import json

import pandas as pd
from flask import render_template_string

from dashboards.utils import ALL_FILTER_VALUE


MONTH_LABELS_FULL = {
    1: "Janvier",
    2: "Fevrier",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Aout",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Decembre",
}
MONTH_LABELS_SHORT = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Avr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Aou",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}
MONTH_LABELS_UPPER = {
    1: "JAN",
    2: "FEV",
    3: "MAR",
    4: "AVR",
    5: "MAI",
    6: "JUN",
    7: "JUL",
    8: "AOU",
    9: "SEP",
    10: "OCT",
    11: "NOV",
    12: "DEC",
}

SOLAR_STATUS_OK = "MONGODB CONNECTE"
SOLAR_STATUS_DEGRADED = "SOURCE DEGRADEE"
SOLAR_DEFAULT_MESSAGE = (
    "MongoDB connecte. Cette page agrege la telemetrie horaire pour suivre "
    "la puissance AC/DC, l'irradiation, les temperatures et le yield par pays."
)

SOLAR_TEMPLATE = """<!DOCTYPE html>
<html lang=\"fr\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<title>Solar Observatory - Telemetry Deck</title>
<link href=\"https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=IBM+Plex+Mono:wght@300;400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap\" rel=\"stylesheet\">
<link rel=\"stylesheet\" href=\"{{ url_for('solar_assets', filename='solar_observatory.css') }}\">
</head>
<body class=\"solar-observatory-body\">
<script id=\"solar-observatory-payload\" type=\"application/json\">{{ payload_json | safe }}</script>
<div class=\"solar-observatory-root\">
<div class=\"wrapper\">

  <div class=\"topbar anim anim-1\">
    <div class=\"topbar-left\">
      <div class=\"observatory-badge\">SOLAR OBSERVATORY</div>
    </div>
    <div class=\"topbar-center\">SOLAR TELEMETRY PERFORMANCE SYSTEM v3.0</div>
    <div class=\"topbar-right\">
      <a href=\"/\" class=\"export-button solar-home-link no-print\">Retour accueil</a>
      <button type=\"button\" id=\"solar-export-csv-button\" class=\"solar-export-btn no-print\">&#11015; CSV</button>
      <button type=\"button\" id=\"solar-export-excel-button\" class=\"solar-export-btn solar-export-btn--excel no-print\">&#11015; Excel</button>
      <button type=\"button\" class=\"export-button no-print\" id=\"solar-export-pdf-button\">Exporter PDF</button>
      <div class=\"status-dot\"></div>
      <span id=\"mongo-status-label\">{{ status_label }}</span>
      <span>&nbsp;.&nbsp;</span>
      <span id=\"live-time\">--:--:--</span>
    </div>
  </div>

  <div class=\"hero anim anim-2\" style=\"margin-top:3px;\">
    <div class=\"hero-main\">
      <div>
        <div class=\"hero-eyebrow\">Solar Telemetry Deck</div>
        <h1 class=\"hero-title\">Solar<br><span>Observatory</span><br>Analytics</h1>
        <div class=\"hero-date\" id=\"hero-date\">{{ metrics.period_label }}</div>
        <p class=\"hero-desc\">Lecture quotidienne agregee depuis la telemetrie horaire: puissance AC/DC, irradiation, temperature ambiante, temperature module et yield sur le portefeuille observe.</p>
        <div class=\"badges\">
          <span class=\"badge badge-amber\" id=\"hero-badge-records\">{{ metrics.telemetry_count }} points horaires</span>
          <span class=\"badge badge-teal\" id=\"hero-badge-months\">{{ metrics.active_days }} jours</span>
          <span class=\"badge badge-ghost\" id=\"hero-badge-source\">{{ metrics.source_label }}</span>
        </div>
      </div>
    </div>
    <div class=\"hero-side\">
      <div class=\"side-card\">
        <div class=\"card-eyebrow\">Fenetre Observee</div>
        <div class=\"card-title\" id=\"side-period-title\">{{ metrics.period_label }}</div>
        <p class=\"card-desc\">Vue journali&egrave;re calcul&eacute;e &agrave; partir des relev&eacute;s horaires disponibles pour chaque pays.</p>
      </div>
      <div class=\"side-card\">
        <div class=\"card-eyebrow\">Moteur du Score</div>
        <div class=\"card-title\" id=\"side-source-title\">{{ metrics.source_label }}</div>
        <p class=\"card-desc\">Le rendement traduit ici le ratio AC/DC sur les heures productives du systeme.</p>
      </div>
    </div>
  </div>

  <div class=\"stat-strip anim anim-3\">
    <div class=\"stat-card\">
      <div class=\"stat-eyebrow\">Releves Horaires</div>
      <div class=\"stat-value amber\" id=\"s-releves\">{{ metrics.telemetry_count }}</div>
      <div class=\"stat-label\">Volume horaire retenu pour<br>la lecture active</div>
    </div>
    <div class=\"stat-card\">
      <div class=\"stat-eyebrow\">Pays Actifs</div>
      <div class=\"stat-value teal\" id=\"s-mois\">{{ metrics.active_scopes }}</div>
      <div class=\"stat-label\">Nombre de pays visibles<br>dans la selection</div>
    </div>
    <div class=\"stat-card\">
      <div class=\"stat-eyebrow\">Puissance AC moy.</div>
      <div class=\"stat-value\" id=\"s-eff\">{{ metrics.avg_ac_power }}</div>
      <div class=\"stat-label\">Niveau moyen de sortie<br>sur la fenetre selectionnee</div>
    </div>
    <div class=\"stat-card\">
      <div class=\"stat-eyebrow\">Rendement Onduleur</div>
      <div class=\"stat-value\" id=\"s-growth\">{{ metrics.avg_efficiency }}</div>
      <div class=\"stat-label\">Conversion moyenne<br>AC sur DC productif</div>
    </div>
  </div>

  <div class=\"main-grid anim anim-4\">
    <div class=\"chart-panel\">
      <div class=\"panel-eyebrow\">Power Curve</div>
      <div class=\"panel-title\">Trajectoire quotidienne puissance / irradiation</div>
      <div class=\"legend\">
        <div class=\"legend-item\"><div class=\"legend-dot\" style=\"background:var(--amber)\"></div>Puissance AC</div>
        <div class=\"legend-item\"><div class=\"legend-dot\" style=\"background:var(--teal)\"></div>Puissance DC</div>
        <div class=\"legend-item\"><div class=\"legend-dot\" style=\"background:#8B6DFF\"></div>Irradiation</div>
      </div>
      <div class=\"chart-wrap\">
        <canvas id=\"dailyChart\"></canvas>
      </div>
    </div>

    <div class=\"control-tray\">
      <div class=\"control-card\">
        <div class=\"panel-eyebrow\">Control Tray</div>
        <div class=\"panel-title\" style=\"font-size:14px; margin-bottom:4px;\">Cadrez la fenetre d'observation</div>
        <p style=\"font-size:12px; color:var(--data); line-height:1.6; margin-bottom:16px;\">{{ status_message }}</p>
        <div class=\"card-eyebrow\" style=\"margin-bottom:4px;\">Perimetre</div>
        <p style=\"font-size:11px; color:var(--muted); line-height:1.5;\">Le filtre principal bascule entre les pays disponibles. Les courbes restent journali&egrave;res pour garder la lecture fluide.</p>
        <select class=\"select-styled\" id=\"solar-company-filter\">
          {% for option in scope_options %}
          <option value=\"{{ option.value }}\" {% if option.value == selected_scope %}selected{% endif %}>{{ option.label }}</option>
          {% endfor %}
        </select>
        <div class="filter-stack">
          <div class="filter-field">
            <label class="filter-label" for="solar-month-filter">Mois</label>
            <select class="select-styled" id="solar-month-filter">
              <option value="__all__">Tous les mois</option>
            </select>
          </div>
          <div class="date-filter-grid">
            <div class="filter-field">
              <label class="filter-label" for="solar-start-date-filter">Debut</label>
              <input class="input-styled" type="date" id="solar-start-date-filter">
            </div>
            <div class="filter-field">
              <label class="filter-label" for="solar-end-date-filter">Fin</label>
              <input class="input-styled" type="date" id="solar-end-date-filter">
            </div>
          </div>
        </div>
      </div>

      <div class=\"weather-grid\">
        <div class=\"weather-mini\">
          <div class=\"stat-eyebrow\">Irradiation moy.</div>
          <div class=\"weather-val\" id=\"temp-avg-value\">{{ metrics.avg_irradiation }}</div>
          <div class=\"weather-sub\">Energie solaire<br>recue en moyenne</div>
        </div>
        <div class=\"weather-mini\">
          <div class=\"stat-eyebrow\">Yield Jour.</div>
          <div class=\"weather-val\" id=\"humidity-avg-value\">{{ metrics.avg_daily_yield }}</div>
          <div class=\"weather-sub\">Production journali&egrave;re<br>moyenne</div>
        </div>
        <div class=\"weather-mini\">
          <div class=\"stat-eyebrow\">Temp. Amb.</div>
          <div class=\"weather-val\" id=\"wind-avg-value\">{{ metrics.avg_ambient_temperature }}</div>
          <div class=\"weather-sub\">Contexte thermique<br>ambiant</div>
        </div>
        <div class=\"weather-mini\">
          <div class=\"stat-eyebrow\">Temp. Module</div>
          <div class=\"weather-val\" id=\"pressure-avg-value\">{{ metrics.avg_module_temperature }}</div>
          <div class=\"weather-sub\">Charge thermique<br>des panneaux</div>
        </div>
      </div>

      <div class=\"control-card\">
        <div class=\"panel-eyebrow\">Monthly Pulse</div>
        <div class=\"panel-title\" style=\"font-size:13px; margin-bottom:12px;\">Profil mensuel de la puissance AC et du yield journalier</div>
        <div class=\"chart-wrap\" style=\"height:160px;\">
          <canvas id=\"monthlyChart\"></canvas>
        </div>
      </div>
    </div>
  </div>

  <div class=\"bottom-row anim anim-5\">
    <div class=\"charts-row\">
      <div class=\"chart-panel\">
        <div class=\"panel-eyebrow\">Thermal Signal</div>
        <div class=\"panel-title\" style=\"font-size:14px;\">Comment la temperature module tire le rendement</div>
        <div class=\"chart-wrap\" style=\"height:200px;\">
          <canvas id=\"thermalChart\"></canvas>
        </div>
      </div>
      <div class=\"chart-panel\">
        <div class=\"panel-eyebrow\">Thermal Context</div>
        <div class=\"panel-title\" style=\"font-size:14px;\">Lecture conjointe des temperatures ambiante et module</div>
        <div class=\"chart-wrap\" style=\"height:200px;\">
          <canvas id=\"meteoChart\"></canvas>
        </div>
      </div>
    </div>

    <div class=\"chart-panel\" style=\"display:flex;flex-direction:column;justify-content:space-between;\">
      <div>
        <div class=\"panel-eyebrow\">Signal Overlay</div>
        <div class=\"panel-title\" style=\"font-size:14px;\">Dispersion irradiation / puissance AC</div>
        <div class=\"chart-wrap\" style=\"height:200px;\">
          <canvas id=\"scatterChart\"></canvas>
        </div>
      </div>
    </div>
  </div>

  <div class=\"table-area anim anim-6\">
    <div class=\"table-panel\">
      <div class=\"panel-eyebrow\">Daily Observations</div>
      <div class=\"panel-title\">R&eacute;sum&eacute; journalier d&eacute;taill&eacute;</div>
      <div style=\"overflow-x:auto;\">
        <table id=\"rawTable\">
          <thead>
            <tr>
              <th>Date</th>
              <th>Pays</th>
              <th>AC</th>
              <th>DC</th>
              <th>Irrad.</th>
              <th>Yield</th>
              <th>Eff.</th>
            </tr>
          </thead>
          <tbody id=\"rawTableBody\"></tbody>
        </table>
      </div>
    </div>

    <div class=\"digest-panel\">
      <div class=\"panel-eyebrow\">Monthly Digest</div>
      <div class=\"panel-title\" style=\"font-size:14px;\">R&eacute;sum&eacute; mensuel</div>
      <table id=\"digestTable\">
        <thead>
          <tr>
            <th>Mois</th>
            <th>Jours</th>
            <th>AC moy.</th>
            <th>Yield jour.</th>
          </tr>
        </thead>
        <tbody id=\"digestBody\"></tbody>
      </table>
    </div>
  </div>

</div>
</div>
<script src=\"https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js\"></script>
<script src=\"https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js\"></script>
<script src=\"{{ url_for('solar_assets', filename='solar_observatory.js') }}\"></script>
</body>
</html>
"""


def _normalize_percentage(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None

    numeric_value = float(value)
    if abs(numeric_value) <= 1.5:
        return numeric_value * 100
    return numeric_value


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_round(value: object, digits: int = 1) -> float | None:
    numeric_value = _optional_float(value)
    if numeric_value is None:
        return None
    return round(numeric_value, digits)


def _humanize_source(source: object) -> str:
    label = str(source or "ac_dc_ratio").strip().replace("_", " ")
    return " ".join(part.upper() if len(part) <= 3 else part.title() for part in label.split())


def _prepare_solar_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    prepared = dataframe.copy()

    if "timestamp" in prepared.columns:
        prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", dayfirst=True)
    elif "datetime" in prepared.columns:
        prepared["timestamp"] = pd.to_datetime(prepared["datetime"], errors="coerce", dayfirst=True)
    elif "date" in prepared.columns and "time" in prepared.columns:
        prepared["timestamp"] = pd.to_datetime(
            prepared["date"].astype(str).str.strip() + " " + prepared["time"].astype(str).str.strip(),
            errors="coerce",
            dayfirst=True,
        )
    elif "date" in prepared.columns:
        prepared["timestamp"] = pd.to_datetime(prepared["date"], errors="coerce", dayfirst=True)
    else:
        prepared["timestamp"] = pd.NaT

    if "date" not in prepared.columns:
        prepared["date"] = prepared["timestamp"].dt.normalize()
    else:
        prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce", dayfirst=True)
        prepared["date"] = prepared["date"].fillna(prepared["timestamp"].dt.normalize())

    for column in [
        "production_efficiency",
        "ac_power",
        "dc_power",
        "irradiation",
        "ambient_temperature",
        "module_temperature",
        "daily_yield",
        "total_yield",
        "year",
        "month",
        "day",
        "hour",
    ]:
        if column in prepared.columns:
            prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
        else:
            prepared[column] = pd.Series([pd.NA] * len(prepared), index=prepared.index)

    if "company" not in prepared.columns:
        if "country" in prepared.columns:
            prepared["company"] = prepared["country"]
        else:
            prepared["company"] = "Solar Portfolio"

    if "production_efficiency" not in prepared.columns and {"ac_power", "dc_power"}.issubset(prepared.columns):
        prepared["production_efficiency"] = prepared["ac_power"].divide(
            prepared["dc_power"].where(prepared["dc_power"] > 0)
        ).multiply(100)

    if "production_efficiency_source" not in prepared.columns:
        prepared["production_efficiency_source"] = "ac_dc_ratio"

    prepared["company"] = prepared["company"].fillna("Solar Portfolio").astype(str).str.strip()
    prepared["production_efficiency_source"] = (
        prepared["production_efficiency_source"].fillna("ac_dc_ratio").astype(str).str.strip()
    )

    prepared = prepared.dropna(subset=["timestamp"]).copy()
    prepared["year"] = prepared.get("year", prepared["timestamp"].dt.year).fillna(prepared["timestamp"].dt.year).astype("Int64")
    prepared["month"] = prepared.get("month", prepared["timestamp"].dt.month).fillna(prepared["timestamp"].dt.month).astype("Int64")

    return prepared.sort_values(["company", "timestamp"], kind="stable").reset_index(drop=True)


def _build_daily_frame(prepared: pd.DataFrame) -> pd.DataFrame:
    if prepared.empty:
        return pd.DataFrame(
            columns=[
                "company",
                "date",
                "year",
                "month",
                "observations",
                "ac_power",
                "dc_power",
                "irradiation",
                "ambient_temperature",
                "module_temperature",
                "daily_yield",
                "total_yield",
                "production_efficiency",
                "production_efficiency_source",
            ]
        )

    daily_frame = (
        prepared.assign(observation_date=prepared["timestamp"].dt.normalize())
        .groupby(["company", "observation_date"], dropna=False, as_index=False)
        .agg(
            year=("year", "first"),
            month=("month", "first"),
            observations=("timestamp", "size"),
            ac_power=("ac_power", "mean"),
            dc_power=("dc_power", "mean"),
            irradiation=("irradiation", "mean"),
            ambient_temperature=("ambient_temperature", "mean"),
            module_temperature=("module_temperature", "mean"),
            daily_yield=("daily_yield", "max"),
            total_yield=("total_yield", "max"),
            production_efficiency=("production_efficiency", "mean"),
            production_efficiency_source=("production_efficiency_source", "first"),
        )
        .rename(columns={"observation_date": "date"})
        .sort_values(["date", "company"], kind="stable")
        .reset_index(drop=True)
    )
    return daily_frame


def _format_period(records: list[dict[str, object]]) -> str:
    if not records:
        return "PERIODE INDISPONIBLE"

    start_date = pd.to_datetime(records[0]["date_iso"])
    end_date = pd.to_datetime(records[-1]["date_iso"])
    start_label = f"{start_date:%d} {MONTH_LABELS_UPPER.get(start_date.month, start_date.strftime('%b').upper())} {start_date:%Y}"
    end_label = f"{end_date:%d} {MONTH_LABELS_UPPER.get(end_date.month, end_date.strftime('%b').upper())} {end_date:%Y}"
    return f"{start_label} -> {end_label}"


def _build_scope_options(prepared: pd.DataFrame) -> list[dict[str, str]]:
    options = [{"label": "Tous les perimetres", "value": ALL_FILTER_VALUE}]

    companies = sorted(
        {
            value
            for value in prepared.get("company", pd.Series(dtype="object")).dropna().astype(str)
            if value
        }
    )
    if len(companies) > 1:
        options.extend({"label": company, "value": f"company::{company}"} for company in companies)
        return options

    if prepared.empty:
        return options

    periods = prepared["date"].dt.to_period("M").dropna().unique().tolist()
    for period in periods:
        timestamp = period.to_timestamp()
        label = f"{MONTH_LABELS_FULL.get(timestamp.month, timestamp.strftime('%B'))} {timestamp.year}"
        options.append({"label": label, "value": f"period::{period}"})

    return options


def _serialize_records(prepared: pd.DataFrame) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row in prepared.itertuples(index=False):
        date_value = pd.to_datetime(getattr(row, "date", pd.NaT), errors="coerce")
        if pd.isna(date_value):
            continue

        month_value = int(getattr(row, "month", date_value.month) or date_value.month)
        year_value = int(getattr(row, "year", date_value.year) or date_value.year)
        efficiency_value = _normalize_percentage(getattr(row, "production_efficiency", None))
        records.append(
            {
                "date_iso": date_value.strftime("%Y-%m-%d"),
                "date_axis": date_value.strftime("%d/%m"),
                "month_short": MONTH_LABELS_SHORT.get(month_value, str(month_value)),
                "month_label": MONTH_LABELS_FULL.get(month_value, str(month_value)),
                "month_digest": f"{MONTH_LABELS_SHORT.get(month_value, str(month_value))} {year_value}",
                "period_key": f"{year_value:04d}-{month_value:02d}",
                "company": str(getattr(row, "company", "Solar Portfolio") or "Solar Portfolio"),
                "observations": int(getattr(row, "observations", 0) or 0),
                "ac_power": _optional_round(getattr(row, "ac_power", None), 1),
                "dc_power": _optional_round(getattr(row, "dc_power", None), 1),
                "irradiation": _optional_round(getattr(row, "irradiation", None), 3),
                "ambient_temperature": _optional_round(getattr(row, "ambient_temperature", None), 1),
                "module_temperature": _optional_round(getattr(row, "module_temperature", None), 1),
                "daily_yield": _optional_round(getattr(row, "daily_yield", None), 1),
                "total_yield": _optional_round(getattr(row, "total_yield", None), 1),
                "efficiency": _optional_round(efficiency_value, 1),
                "source": str(getattr(row, "production_efficiency_source", "ac_dc_ratio") or "ac_dc_ratio"),
            }
        )
    return records


def _numeric_values(records: list[dict[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for record in records:
        value = record.get(key)
        if value is None:
            continue
        values.append(float(value))
    return values


def _average(records: list[dict[str, object]], key: str) -> float:
    values = _numeric_values(records, key)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _maximum(records: list[dict[str, object]], key: str) -> float:
    values = _numeric_values(records, key)
    if not values:
        return 0.0
    return max(values)


def _build_metrics(records: list[dict[str, object]]) -> dict[str, str]:
    if not records:
        return {
            "telemetry_count": "0",
            "active_days": "0",
            "active_scopes": "0",
            "avg_ac_power": "0.0 kW",
            "avg_efficiency": "0.0%",
            "avg_irradiation": "0.00",
            "avg_daily_yield": "0.0",
            "avg_ambient_temperature": "0.0 C",
            "avg_module_temperature": "0.0 C",
            "peak_ac_power": "0.0 kW",
            "period_label": "PERIODE INDISPONIBLE",
            "source_label": "AC/DC Ratio",
        }

    telemetry_count = sum(int(record.get("observations", 0) or 0) for record in records)
    active_days = len(records)
    active_scopes = len({record["company"] for record in records if record.get("company")})

    return {
        "telemetry_count": str(telemetry_count),
        "active_days": str(active_days),
        "active_scopes": str(active_scopes),
        "avg_ac_power": f"{_average(records, 'ac_power'):.1f} kW",
        "avg_efficiency": f"{_average(records, 'efficiency'):.1f}%",
        "avg_irradiation": f"{_average(records, 'irradiation'):.2f}",
        "avg_daily_yield": f"{_average(records, 'daily_yield'):.1f}",
        "avg_ambient_temperature": f"{_average(records, 'ambient_temperature'):.1f} C",
        "avg_module_temperature": f"{_average(records, 'module_temperature'):.1f} C",
        "peak_ac_power": f"{_maximum(records, 'ac_power'):.1f} kW",
        "period_label": _format_period(records),
        "source_label": _humanize_source(records[0].get("source", "ac_dc_ratio")),
    }


def _build_payload(records: list[dict[str, object]], error_message: str | None) -> str:
    payload = {
        "status_label": SOLAR_STATUS_DEGRADED if error_message else SOLAR_STATUS_OK,
        "status_message": error_message or SOLAR_DEFAULT_MESSAGE,
        "records": records,
        "metrics": _build_metrics(records),
    }
    return json.dumps(payload, ensure_ascii=False)


def render_solar_observatory_page(dataframe: pd.DataFrame, error_message: str | None = None) -> str:
    prepared = _prepare_solar_dataframe(dataframe)
    daily_frame = _build_daily_frame(prepared)
    records = _serialize_records(daily_frame)
    metrics = _build_metrics(records)

    return render_template_string(
        SOLAR_TEMPLATE,
        metrics=metrics,
        payload_json=_build_payload(records, error_message),
        scope_options=_build_scope_options(daily_frame),
        selected_scope=ALL_FILTER_VALUE,
        status_label=SOLAR_STATUS_DEGRADED if error_message else SOLAR_STATUS_OK,
        status_message=error_message or SOLAR_DEFAULT_MESSAGE,
    )



