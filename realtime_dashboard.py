#!/usr/bin/env python3

from pathlib import Path

import pandas as pd

from flask import Flask, jsonify, render_template, send_file

from dashboard_health import build_health_report

BASE_DIR = Path("/home/pi/eng402_gateway_data")
PROCESSED_DIR = BASE_DIR / "processed"

FIGURES_DIR = BASE_DIR / "figures"
LOG_DIR = BASE_DIR / "logs"

SYSTEM_LOG_FILES = {
    "USB Backup": LOG_DIR / "usb_sync.log",
    "Gateway Service": LOG_DIR / "gateway_service.log",
    "Gateway Errors": LOG_DIR / "gateway_service_error.log",
    "Processing Service": LOG_DIR / "processing_service.log",
    "Processing Errors": LOG_DIR / "processing_service_error.log",
}

ANALYSIS_FIGURE_PATTERNS = {
    "temperature": [
        "temperature_timeseries_*.png",
    ],
    "pressure": [
        "pressure_timeseries_*.png",
    ],
    "idw": [
        "idw_temperature_map_*.png",
        "idw_temperature_*.png",
        "*idw*temperature*.png",
    ],
    "frost": [
        "frost_risk_*.png",
        "*frost*risk*.png",
    ],
}

app = Flask(__name__)

def current_period_label() -> str:

    now = pd.Timestamp.now()
    period_start = now.normalize() + pd.Timedelta(
        hours=now.hour
    )

    return period_start.strftime("%Y-%m-%d_%H")

def latest_processed_file() -> Path | None:

    preferred_file = (
        PROCESSED_DIR
        / f"processed_data_{current_period_label()}.csv"
    )

    if preferred_file.exists():
        return preferred_file

    files = sorted(
        PROCESSED_DIR.glob("processed_data_*_??.csv")
    )

    if not files:
        files = sorted(
            PROCESSED_DIR.glob("processed_data_*.csv")
        )

    return files[-1] if files else None

def load_processed_data() -> tuple[pd.DataFrame, Path | None]:

    csv_file = latest_processed_file()

    if csv_file is None:
        return pd.DataFrame(), None

    try:
        df = pd.read_csv(csv_file)
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame(), csv_file

    if df.empty:
        return df, csv_file

    df["receive_time"] = pd.to_datetime(
        df["receive_time"],
        errors="coerce",
    )

    numeric_columns = [
        "sequence",
        "temperature_c",
        "humidity_percent",
        "pressure_hpa",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    return df, csv_file

def latest_sensor_records(
    df: pd.DataFrame,
) -> list[dict]:

    if df.empty:
        return []

    latest = (
        df.dropna(subset=["sensor_name"])
        .sort_values("receive_time")
        .groupby("sensor_name", as_index=False)
        .tail(1)
        .sort_values("sensor_name")
        .copy()
    )

    latest["receive_time"] = latest[
        "receive_time"
    ].astype(str)

    return latest.to_dict("records")

def make_time_series(
    df: pd.DataFrame,
    value_column: str,
    max_points: int = 120,
) -> dict:

    if (
        df.empty
        or value_column not in df.columns
        or "sensor_name" not in df.columns
    ):
        return {
            "labels": [],
            "datasets": [],
        }

    valid_df = df.dropna(
        subset=[
            "receive_time",
            "sensor_name",
            value_column,
        ]
    ).copy()

    if valid_df.empty:
        return {
            "labels": [],
            "datasets": [],
        }

    pivot = (
        valid_df.pivot_table(
            index="receive_time",
            columns="sensor_name",
            values=value_column,
            aggfunc="last",
        )
        .sort_index()
        .tail(max_points)
    )

    labels = [
        timestamp.strftime("%H:%M:%S")
        for timestamp in pivot.index
    ]

    datasets = []

    for sensor_name in sorted(pivot.columns):
        values = []

        for value in pivot[sensor_name]:
            if pd.isna(value):
                values.append(None)
            else:
                values.append(round(float(value), 3))

        datasets.append(
            {
                "label": sensor_name,
                "data": values,
            }
        )

    return {
        "labels": labels,
        "datasets": datasets,
    }

def make_packet_series(
    df: pd.DataFrame,
    max_points: int = 120,
) -> dict:

    if df.empty:
        return {
            "labels": [],
            "datasets": [],
        }

    valid_df = df.dropna(
        subset=["receive_time", "sensor_name"]
    ).copy()

    if valid_df.empty:
        return {
            "labels": [],
            "datasets": [],
        }

    valid_df["packet_count"] = (
        valid_df.groupby("sensor_name").cumcount() + 1
    )

    pivot = (
        valid_df.pivot_table(
            index="receive_time",
            columns="sensor_name",
            values="packet_count",
            aggfunc="last",
        )
        .sort_index()
        .tail(max_points)
        .ffill()
    )

    labels = [
        timestamp.strftime("%H:%M:%S")
        for timestamp in pivot.index
    ]

    datasets = []

    for sensor_name in sorted(pivot.columns):
        values = [
            None if pd.isna(value)
            else int(value)
            for value in pivot[sensor_name]
        ]

        datasets.append(
            {
                "label": sensor_name,
                "data": values,
            }
        )

    return {
        "labels": labels,
        "datasets": datasets,
    }

def latest_analysis_figure(
    figure_type: str,
) -> Path | None:

    patterns = ANALYSIS_FIGURE_PATTERNS.get(
        figure_type
    )

    if not patterns or not FIGURES_DIR.exists():
        return None

    matching_files = []

    for pattern in patterns:
        matching_files.extend(
            FIGURES_DIR.glob(pattern)
        )

    matching_files = [
        file_path
        for file_path in matching_files
        if file_path.is_file()
    ]

    if not matching_files:
        return None

    return max(
        matching_files,
        key=lambda file_path: file_path.stat().st_mtime,
    )

@app.route("/analysis/<figure_type>")
def analysis_figure(figure_type: str):

    figure_path = latest_analysis_figure(
        figure_type
    )

    if figure_path is None:
        return (
            "Analysis figure is not available.",
            404,
        )

    return send_file(
        figure_path,
        mimetype="image/png",
        conditional=True,
        max_age=0,
    )

@app.route("/")

def index():

    df, csv_file = load_processed_data()
    sensors = latest_sensor_records(df)

    if df.empty:
        updated = "No processed data"
    else:
        latest_time = df["receive_time"].max()

        updated = (
            latest_time.strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
            if pd.notna(latest_time)
            else "Unavailable"
        )

    return render_template(
        "index.html",
        sensors=sensors,
        updated=updated,
        source_file=(
            csv_file.name
            if csv_file is not None
            else "None"
        ),
    )

def read_recent_log_lines(
    file_path: Path,
    maximum_lines: int = 30,
) -> list[str]:

    if not file_path.exists():
        return []

    try:
        lines = file_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError:
        return []

    return [
        line
        for line in lines[-maximum_lines:]
        if line.strip()
    ]

@app.route("/api/logs")
def system_logs():

    log_groups = []

    for title, file_path in SYSTEM_LOG_FILES.items():
        log_groups.append(
            {
                "title": title,
                "file": file_path.name,
                "lines": read_recent_log_lines(
                    file_path
                ),
            }
        )

    return jsonify(
        {
            "generated_at":
                pd.Timestamp.now().isoformat(),
            "logs": log_groups,
        }
    )

@app.route("/api/health")
def health():

    df, csv_file = load_processed_data()
    report = build_health_report(df)

    report["source_file"] = (
        csv_file.name
        if csv_file is not None
        else None
    )

    return jsonify(report)

@app.route("/api/charts")
def charts():

    df, csv_file = load_processed_data()

    return jsonify(
        {
            "period": current_period_label(),
            "source_file": (
                csv_file.name
                if csv_file is not None
                else None
            ),
            "packet_count": make_packet_series(df),
            "temperature": make_time_series(
                df,
                "temperature_c",
            ),
            "humidity": make_time_series(
                df,
                "humidity_percent",
            ),
            "pressure": make_time_series(
                df,
                "pressure_hpa",
            ),
        }
    )

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )
