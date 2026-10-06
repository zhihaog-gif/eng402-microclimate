#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path("/home/pi/eng402_gateway_data")
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"
ERROR_DIR = BASE_DIR / "errors"
LOG_DIR = BASE_DIR / "logs"
CONFIG_FILE = BASE_DIR / "config" / "nodes.json"

LOG_FILE = LOG_DIR / "data_processing.log"

NOW = pd.Timestamp.now()
TODAY = NOW.strftime("%Y-%m-%d")

PERIOD_HOUR = NOW.hour
PERIOD_START = NOW.normalize() + pd.Timedelta(hours=PERIOD_HOUR)
PERIOD_END = PERIOD_START + pd.Timedelta(hours=1)
PERIOD_LABEL = PERIOD_START.strftime("%Y-%m-%d_%H")

DATED_RAW_FILE = RAW_DIR / f"sensor_data_{TODAY}.csv"
CURRENT_RAW_FILE = RAW_DIR / "sensor_data.csv"

OUTPUT_FILE = (
    PROCESSED_DIR
    / f"processed_data_{PERIOD_LABEL}.csv"
)

ERROR_FILE = (
    ERROR_DIR
    / f"processing_errors_{PERIOD_LABEL}.csv"
)

MIN_TEMPERATURE_C = -40.0
MAX_TEMPERATURE_C = 85.0

MIN_HUMIDITY_PERCENT = 0.0
MAX_HUMIDITY_PERCENT = 100.0

MIN_PRESSURE_HPA = 300.0
MAX_PRESSURE_HPA = 1100.0

MOVING_AVERAGE_WINDOW = 5
FROST_THRESHOLD_C = 2.0

def write_log(message: str) -> None:

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")

def create_directories() -> None:

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ERROR_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def select_input_file() -> Path:

    if DATED_RAW_FILE.exists():
        return DATED_RAW_FILE

    if CURRENT_RAW_FILE.exists():
        return CURRENT_RAW_FILE

    raise FileNotFoundError(
        "No raw sensor CSV was found. Checked:\n"
        f"  {DATED_RAW_FILE}\n"
        f"  {CURRENT_RAW_FILE}"
    )

def load_node_coordinates() -> dict:

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Node configuration file not found: {CONFIG_FILE}"
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as config_file:
        coordinates = json.load(config_file)

    if not isinstance(coordinates, dict):
        raise ValueError(
            "nodes.json must contain a JSON object."
        )

    return coordinates

def safe_json_loads(raw_value: object) -> tuple[dict, str | None]:

    if pd.isna(raw_value):
        return {}, "raw_json is empty"

    try:
        parsed = json.loads(str(raw_value))

        if not isinstance(parsed, dict):
            return {}, "raw_json is not a JSON object"

        return parsed, None

    except json.JSONDecodeError as error:
        return {}, f"JSON decoding failed: {error}"

def first_available(
    source: dict,
    keys: list[str],
    default: object = np.nan,
) -> object:

    for key in keys:
        if key in source and source[key] is not None:
            return source[key]

    return default

def to_float_or_nan(value: object) -> float:

    if value is None or value == "":
        return np.nan

    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan

def to_boolean(value: object) -> bool:

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "connected",
        }

    return bool(value)

def value_is_valid(
    value: float,
    minimum: float,
    maximum: float,
) -> bool:

    if pd.isna(value):
        return False

    return minimum <= value <= maximum

def select_current_period(raw_df: pd.DataFrame) -> pd.DataFrame:

    raw_df = raw_df.copy()

    raw_df["receive_time"] = pd.to_datetime(
        raw_df["receive_time"],
        errors="coerce",
    )

    period_df = raw_df[
        (raw_df["receive_time"] >= PERIOD_START)
        & (raw_df["receive_time"] < PERIOD_END)
    ].copy()

    if period_df.empty:
        raise ValueError(
            "No raw sensor records were found for the current "
            f"one-hour period: {PERIOD_START} to {PERIOD_END}"
        )

    return period_df

def parse_rows(
    raw_df: pd.DataFrame,
    node_coordinates: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    records: list[dict] = []
    errors: list[dict] = []

    for row_number, row in raw_df.iterrows():
        payload, json_error = safe_json_loads(
            row.get("raw_json")
        )

        receive_time = row.get("receive_time", pd.NaT)

        sensor_name = first_available(
            payload,
            ["sensor_name", "node_name"],
            row.get("sensor_name", ""),
        )

        sensor_name = str(sensor_name).strip()

        coordinates = node_coordinates.get(
            sensor_name,
            {"x": np.nan, "y": np.nan},
        )

        node_id = first_available(
            payload,
            ["node_id"],
            row.get("node_id", np.nan),
        )

        sequence = first_available(
            payload,
            ["sequence"],
            row.get("sequence", np.nan),
        )

        mesh_time_us = first_available(
            payload,
            ["mesh_time_us"],
            row.get("mesh_time_us", np.nan),
        )

        temperature_c = to_float_or_nan(
            first_available(
                payload,
                [
                    "temperature_c",
                    "temperature",
                    "temp_c",
                ],
            )
        )

        humidity_percent = to_float_or_nan(
            first_available(
                payload,
                [
                    "humidity_percent",
                    "humidity",
                    "humidity_pct",
                ],
            )
        )

        pressure_hpa = to_float_or_nan(
            first_available(
                payload,
                [
                    "pressure_hpa",
                    "pressure",
                    "pressure_hPa",
                ],
            )
        )

        bmp_connected = to_boolean(
            first_available(
                payload,
                [
                    "bmp280_connected",
                    "bme280_connected",
                    "sensor_connected",
                ],
                False,
            )
        )

        device_error = first_available(
            payload,
            ["error"],
            "",
        )

        temperature_valid = value_is_valid(
            temperature_c,
            MIN_TEMPERATURE_C,
            MAX_TEMPERATURE_C,
        )

        humidity_valid = value_is_valid(
            humidity_percent,
            MIN_HUMIDITY_PERCENT,
            MAX_HUMIDITY_PERCENT,
        )

        pressure_valid = value_is_valid(
            pressure_hpa,
            MIN_PRESSURE_HPA,
            MAX_PRESSURE_HPA,
        )

        communication_status = (
            "Received"
            if json_error is None and sensor_name
            else "Invalid"
        )

        environmental_status = (
            "Valid"
            if (
                bmp_connected
                and temperature_valid
                and pressure_valid
            )
            else "Unavailable"
        )

        records.append(
            {
                "receive_time": receive_time,
                "sensor_name": sensor_name,
                "node_id": node_id,
                "sequence": sequence,
                "mesh_time_us": mesh_time_us,
                "x": coordinates.get("x", np.nan),
                "y": coordinates.get("y", np.nan),
                "bmp_connected": bmp_connected,
                "temperature_c": temperature_c,
                "humidity_percent": humidity_percent,
                "pressure_hpa": pressure_hpa,
                "temperature_valid": temperature_valid,
                "humidity_valid": humidity_valid,
                "pressure_valid": pressure_valid,
                "communication_status": communication_status,
                "environmental_status": environmental_status,
                "device_error": device_error,
                "source_row": row_number + 2,
            }
        )

        if json_error is not None:
            errors.append(
                {
                    "source_row": row_number + 2,
                    "receive_time": receive_time,
                    "sensor_name": sensor_name,
                    "error_type": "JSON_PARSE_ERROR",
                    "error_message": json_error,
                    "raw_json": row.get("raw_json", ""),
                }
            )

        if not sensor_name:
            errors.append(
                {
                    "source_row": row_number + 2,
                    "receive_time": receive_time,
                    "sensor_name": "",
                    "error_type": "MISSING_SENSOR_NAME",
                    "error_message": (
                        "No sensor name was found."
                    ),
                    "raw_json": row.get("raw_json", ""),
                }
            )

    return pd.DataFrame(records), pd.DataFrame(errors)

def add_iqr_outlier_flag(
    df: pd.DataFrame,
    value_column: str,
    flag_column: str,
) -> pd.DataFrame:

    df[flag_column] = False

    for _, group in df.groupby("sensor_name"):
        values = group[value_column].dropna()

        if len(values) < 4:
            continue

        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        if pd.isna(iqr) or iqr == 0:
            continue

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        indices = group.index

        df.loc[indices, flag_column] = (
            (df.loc[indices, value_column] < lower_bound)
            | (df.loc[indices, value_column] > upper_bound)
        )

    return df

def add_smoothed_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.sort_values(
        ["sensor_name", "receive_time"]
    ).copy()

    column_pairs = [
        ("temperature_c", "temperature_smooth"),
        ("humidity_percent", "humidity_smooth"),
        ("pressure_hpa", "pressure_smooth"),
    ]

    for source_column, output_column in column_pairs:
        df[output_column] = (
            df.groupby("sensor_name")[source_column]
            .transform(
                lambda values: values.rolling(
                    window=MOVING_AVERAGE_WINDOW,
                    min_periods=1,
                ).mean()
            )
        )

    return df

def process_data() -> None:

    create_directories()

    input_file = select_input_file()
    node_coordinates = load_node_coordinates()

    print(f"Reading raw data from: {input_file}")
    print(
        f"One-hour period: {PERIOD_START} to {PERIOD_END}"
    )

    raw_df = pd.read_csv(input_file)

    required_columns = {
        "receive_time",
        "sensor_name",
        "node_id",
        "sequence",
        "mesh_time_us",
        "raw_json",
    }

    missing_columns = required_columns.difference(
        raw_df.columns
    )

    if missing_columns:
        raise ValueError(
            "The raw CSV is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    period_df = select_current_period(raw_df)

    processed_df, error_df = parse_rows(
        period_df,
        node_coordinates,
    )

    processed_df["receive_time"] = pd.to_datetime(
        processed_df["receive_time"],
        errors="coerce",
    )

    processed_df["sequence"] = pd.to_numeric(
        processed_df["sequence"],
        errors="coerce",
    )

    processed_df["mesh_time_us"] = pd.to_numeric(
        processed_df["mesh_time_us"],
        errors="coerce",
    )

    processed_df = add_iqr_outlier_flag(
        processed_df,
        "temperature_c",
        "temperature_outlier",
    )

    processed_df = add_iqr_outlier_flag(
        processed_df,
        "humidity_percent",
        "humidity_outlier",
    )

    processed_df = add_iqr_outlier_flag(
        processed_df,
        "pressure_hpa",
        "pressure_outlier",
    )

    processed_df = add_smoothed_columns(processed_df)

    processed_df["frost_status"] = np.where(
        processed_df["temperature_smooth"].notna()
        & (
            processed_df["temperature_smooth"]
            <= FROST_THRESHOLD_C
        ),
        "FROST_WARNING",
        "NORMAL_OR_UNAVAILABLE",
    )

    processed_df = processed_df.sort_values(
        ["receive_time", "sensor_name"]
    )

    processed_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    error_columns = [
        "source_row",
        "receive_time",
        "sensor_name",
        "error_type",
        "error_message",
        "raw_json",
    ]

    if error_df.empty:
        error_df = pd.DataFrame(
            columns=error_columns
        )

    error_df.to_csv(
        ERROR_FILE,
        index=False,
    )

    received_count = int(
        (
            processed_df["communication_status"]
            == "Received"
        ).sum()
    )

    environmental_count = int(
        (
            processed_df["environmental_status"]
            == "Valid"
        ).sum()
    )

    log_message = (
        f"period={PERIOD_LABEL}; "
        f"input_file={input_file.name}; "
        f"raw_rows={len(raw_df)}; "
        f"period_rows={len(period_df)}; "
        f"processed_rows={len(processed_df)}; "
        f"received_packets={received_count}; "
        f"valid_environmental_rows={environmental_count}; "
        f"output={OUTPUT_FILE.name}"
    )

    write_log(log_message)

    print()
    print("Processing completed.")
    print(f"Complete raw-file rows: {len(raw_df)}")
    print(f"Current One-hour rows: {len(period_df)}")
    print(f"Output rows: {len(processed_df)}")
    print(
        "Communication packets received: "
        f"{received_count}"
    )
    print(
        "Valid environmental rows: "
        f"{environmental_count}"
    )
    print(f"Processed CSV: {OUTPUT_FILE}")
    print(f"Error CSV: {ERROR_FILE}")

def main() -> int:

    try:
        process_data()
        return 0

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        pd.errors.ParserError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        write_log(f"Processing failed: {error}")
        return 1

    except Exception as error:
        print(
            "UNEXPECTED ERROR: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )

        write_log(
            "Unexpected processing failure: "
            f"{type(error).__name__}: {error}"
        )

        return 1

if __name__ == "__main__":
    raise SystemExit(main())
