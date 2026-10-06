#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path("/home/pi/eng402_gateway_data")
PROCESSED_DIR = BASE_DIR / "processed"
FIGURES_DIR = BASE_DIR / "figures"
CONFIG_FILE = BASE_DIR / "config" / "nodes.json"
LOG_FILE = BASE_DIR / "logs" / "visualisation.log"

NOW = pd.Timestamp.now()
PERIOD_HOUR = NOW.hour

PERIOD_START = NOW.normalize() + pd.Timedelta(hours=PERIOD_HOUR)
PERIOD_LABEL = PERIOD_START.strftime("%Y-%m-%d_%H")

INPUT_FILE = (
    PROCESSED_DIR
    / f"processed_data_{PERIOD_LABEL}.csv"
)

FROST_THRESHOLD_C = 2.0
IDW_POWER = 2
GRID_SIZE = 100

def write_log(message: str) -> None:

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{timestamp} {message}\n")

def load_node_config() -> dict:

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Node configuration file not found: {CONFIG_FILE}"
        )

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError("nodes.json must contain a JSON object.")

    return config

def select_input_file() -> Path:

    if INPUT_FILE.exists():
        return INPUT_FILE

    available_files = sorted(
        PROCESSED_DIR.glob("processed_data_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not available_files:
        raise FileNotFoundError(
            f"No processed CSV files were found in {PROCESSED_DIR}"
        )

    return available_files[0]

def save_packet_count_plot(df: pd.DataFrame) -> Path:

    packet_counts = (
        df.groupby("sensor_name")
        .size()
        .sort_index()
    )

    output_file = FIGURES_DIR / f"packet_count_{PERIOD_LABEL}.png"

    plt.figure(figsize=(8, 5))
    packet_counts.plot(kind="bar")

    plt.xlabel("Sensor")
    plt.ylabel("Packets received")
    plt.title("Packets Received by Sensor")
    plt.xticks(rotation=0)
    plt.tight_layout()

    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    return output_file

def prepare_environmental_data(df: pd.DataFrame) -> pd.DataFrame:

    environmental_df = df.copy()

    environmental_df["receive_time"] = pd.to_datetime(
        environmental_df["receive_time"],
        errors="coerce",
    )

    environmental_df = environmental_df[
        environmental_df["environmental_status"] == "Valid"
    ]

    environmental_df = environmental_df.dropna(
        subset=[
            "receive_time",
            "sensor_name",
            "x",
            "y",
            "temperature_smooth",
        ]
    )

    return environmental_df.sort_values("receive_time")

def save_time_series_plot(
    df: pd.DataFrame,
    value_column: str,
    ylabel: str,
    title: str,
    filename: str,
    include_frost_threshold: bool = False,
) -> Path:

    output_file = FIGURES_DIR / filename

    plt.figure(figsize=(12, 6))

    for sensor_name, group in df.groupby("sensor_name"):
        group = group.sort_values("receive_time")

        plt.plot(
            group["receive_time"],
            group[value_column],
            label=sensor_name,
        )

    if include_frost_threshold:
        plt.axhline(
            y=FROST_THRESHOLD_C,
            linestyle="--",
            label=f"Frost threshold ({FROST_THRESHOLD_C:.1f} °C)",
        )

        frost_rows = df[
            df[value_column] <= FROST_THRESHOLD_C
        ]

        if not frost_rows.empty:
            plt.scatter(
                frost_rows["receive_time"],
                frost_rows[value_column],
                marker="x",
                label="Frost warning",
                zorder=3,
            )

    plt.xlabel("Time")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()

    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    return output_file

def create_latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:

    latest_rows = (
        df.sort_values("receive_time")
        .groupby("sensor_name", as_index=False)
        .tail(1)
    )

    return latest_rows.dropna(
        subset=["x", "y", "temperature_smooth"]
    )

def idw_interpolate(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    points_x: np.ndarray,
    points_y: np.ndarray,
    values: np.ndarray,
    power: float = 2.0,
) -> np.ndarray:

    result = np.zeros_like(grid_x, dtype=float)

    for row_index in range(grid_x.shape[0]):
        for column_index in range(grid_x.shape[1]):
            x_value = grid_x[row_index, column_index]
            y_value = grid_y[row_index, column_index]

            distances = np.sqrt(
                (points_x - x_value) ** 2
                + (points_y - y_value) ** 2
            )

            exact_match = np.where(distances == 0)[0]

            if len(exact_match) > 0:
                result[row_index, column_index] = values[
                    exact_match[0]
                ]
                continue

            weights = 1.0 / np.power(distances, power)

            result[row_index, column_index] = (
                np.sum(weights * values)
                / np.sum(weights)
            )

    return result

def save_idw_temperature_map(
    snapshot: pd.DataFrame,
    node_config: dict,
) -> Path:

    if len(snapshot) < 3:
        raise ValueError(
            "At least three valid sensor nodes are required "
            "for IDW interpolation."
        )

    all_x = [
        float(details["x"])
        for details in node_config.values()
    ]

    all_y = [
        float(details["y"])
        for details in node_config.values()
    ]

    x_padding = max(1.0, (max(all_x) - min(all_x)) * 0.05)
    y_padding = max(1.0, (max(all_y) - min(all_y)) * 0.05)

    x_values = np.linspace(
        min(all_x) - x_padding,
        max(all_x) + x_padding,
        GRID_SIZE,
    )

    y_values = np.linspace(
        min(all_y) - y_padding,
        max(all_y) + y_padding,
        GRID_SIZE,
    )

    grid_x, grid_y = np.meshgrid(x_values, y_values)

    heatmap = idw_interpolate(
        grid_x=grid_x,
        grid_y=grid_y,
        points_x=snapshot["x"].to_numpy(dtype=float),
        points_y=snapshot["y"].to_numpy(dtype=float),
        values=snapshot["temperature_smooth"].to_numpy(
            dtype=float
        ),
        power=IDW_POWER,
    )

    output_file = (
        FIGURES_DIR
        / f"idw_temperature_frost_risk_{PERIOD_LABEL}.png"
    )

    plt.figure(figsize=(9, 7))

    image = plt.imshow(
        heatmap,
        extent=(
            x_values.min(),
            x_values.max(),
            y_values.min(),
            y_values.max(),
        ),
        origin="lower",
        aspect="equal",
    )

    plt.colorbar(
        image,
        label="Estimated temperature (°C)",
    )

    minimum_temperature = float(np.nanmin(heatmap))
    maximum_temperature = float(np.nanmax(heatmap))

    if (
        minimum_temperature
        <= FROST_THRESHOLD_C
        <= maximum_temperature
    ):
        plt.contour(
            grid_x,
            grid_y,
            heatmap,
            levels=[FROST_THRESHOLD_C],
            linewidths=2,
        )

        plt.contourf(
            grid_x,
            grid_y,
            heatmap,
            levels=[
                minimum_temperature - 0.01,
                FROST_THRESHOLD_C,
            ],
            alpha=0.25,
        )

    for _, row in snapshot.iterrows():
        plt.scatter(
            row["x"],
            row["y"],
            marker="o",
            s=80,
        )

        plt.text(
            row["x"] + 0.15,
            row["y"] + 0.15,
            (
                f'{row["sensor_name"]}\n'
                f'{row["temperature_smooth"]:.2f} °C'
            ),
        )

    latest_time = snapshot["receive_time"].max()

    plt.xlabel("X position (m)")
    plt.ylabel("Y position (m)")
    plt.title(
        "IDW Temperature Heatmap and Initial Frost Risk Area\n"
        f"Latest sensor data: {latest_time}"
    )

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    plt.close()

    return output_file

def generate_visualisations() -> None:

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    input_file = select_input_file()
    node_config = load_node_config()

    print(f"Reading processed data from: {input_file}")

    df = pd.read_csv(input_file)

    required_columns = {
        "receive_time",
        "sensor_name",
        "x",
        "y",
        "environmental_status",
        "temperature_smooth",
        "humidity_smooth",
        "pressure_smooth",
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "The processed CSV is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    generated_files: list[Path] = []

    packet_plot = save_packet_count_plot(df)
    generated_files.append(packet_plot)

    environmental_df = prepare_environmental_data(df)

    if environmental_df.empty:
        message = (
            "No valid environmental measurements are available. "
            "The packet-count plot was generated, but temperature, "
            "humidity, pressure, IDW and frost-risk figures were skipped."
        )

        print()
        print(message)
        write_log(message)

    else:
        generated_files.append(
            save_time_series_plot(
                environmental_df,
                value_column="temperature_smooth",
                ylabel="Temperature (°C)",
                title="Multi-node Temperature with Frost Detection",
                filename=f"temperature_timeseries_{PERIOD_LABEL}.png",
                include_frost_threshold=True,
            )
        )

        humidity_df = environmental_df.dropna(
            subset=["humidity_smooth"]
        )

        if not humidity_df.empty:
            generated_files.append(
                save_time_series_plot(
                    humidity_df,
                    value_column="humidity_smooth",
                    ylabel="Humidity (%)",
                    title="Multi-node Humidity",
                    filename=f"humidity_timeseries_{PERIOD_LABEL}.png",
                )
            )

        pressure_df = environmental_df.dropna(
            subset=["pressure_smooth"]
        )

        if not pressure_df.empty:
            generated_files.append(
                save_time_series_plot(
                    pressure_df,
                    value_column="pressure_smooth",
                    ylabel="Pressure (hPa)",
                    title="Multi-node Pressure",
                    filename=f"pressure_timeseries_{PERIOD_LABEL}.png",
                )
            )

        snapshot = create_latest_snapshot(environmental_df)

        if len(snapshot) >= 3:
            generated_files.append(
                save_idw_temperature_map(
                    snapshot=snapshot,
                    node_config=node_config,
                )
            )
        else:
            warning = (
                "IDW heatmap skipped because fewer than three "
                "valid sensor nodes were available."
            )

            print(warning)
            write_log(warning)

    print()
    print("Visualisation completed.")
    print("Generated files:")

    for generated_file in generated_files:
        print(f"  {generated_file}")

    write_log(
        f"Visualisation completed using {input_file.name}; "
        f"generated_files={len(generated_files)}"
    )

def main() -> int:

    try:
        generate_visualisations()
        return 0

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        pd.errors.ParserError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        write_log(f"Visualisation failed: {error}")
        return 1

    except Exception as error:
        print(
            f"UNEXPECTED ERROR: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )

        write_log(
            f"Unexpected visualisation failure: "
            f"{type(error).__name__}: {error}"
        )

        return 1

if __name__ == "__main__":
    raise SystemExit(main())
