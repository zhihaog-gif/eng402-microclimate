#!/usr/bin/env python3

from pathlib import Path

import pandas as pd

BASE_DIR = Path("/home/pi/eng402_gateway_data")
PROCESSED_DIR = BASE_DIR / "processed"

NOW = pd.Timestamp.now()
PERIOD_HOUR = NOW.hour
PERIOD_START = NOW.normalize() + pd.Timedelta(hours=PERIOD_HOUR)
PERIOD_LABEL = PERIOD_START.strftime("%Y-%m-%d_%H")

INPUT_FILE = ( PROCESSED_DIR / f"processed_data_{PERIOD_LABEL}.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR
    / f"mesh_statistics_{PERIOD_LABEL}.csv"
)

def analyse_mesh() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Processed input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns = {
        "sensor_name",
        "sequence",
        "receive_time",
        "communication_status",
    }

    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            "Processed CSV is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    df["receive_time"] = pd.to_datetime(
        df["receive_time"],
        errors="coerce",
    )

    df["sequence"] = pd.to_numeric(
        df["sequence"],
        errors="coerce",
    )

    results = []

    for sensor_name, group in df.groupby("sensor_name"):
        valid_group = group.dropna(
            subset=["sequence"]
        ).copy()

        if valid_group.empty:
            continue

        sequences = sorted(
            valid_group["sequence"]
            .astype(int)
            .drop_duplicates()
            .tolist()
        )

        received_packets = len(sequences)
        first_sequence = sequences[0]
        last_sequence = sequences[-1]

        expected_packets = (
            last_sequence - first_sequence + 1
        )

        missing_packets = max(
            0,
            expected_packets - received_packets,
        )

        packet_loss_percent = (
            100.0 * missing_packets / expected_packets
            if expected_packets > 0
            else 0.0
        )

        first_time = valid_group["receive_time"].min()
        last_time = valid_group["receive_time"].max()

        duration_seconds = (
            (last_time - first_time).total_seconds()
            if pd.notna(first_time)
            and pd.notna(last_time)
            else 0.0
        )

        packet_rate_per_minute = (
            received_packets / (duration_seconds / 60.0)
            if duration_seconds > 0
            else 0.0
        )

        results.append(
            {
                "Sensor": sensor_name,
                "Packets Received": received_packets,
                "First Sequence": first_sequence,
                "Last Sequence": last_sequence,
                "Expected Packets": expected_packets,
                "Missing Packets": missing_packets,
                "Packet Loss (%)": round(
                    packet_loss_percent,
                    3,
                ),
                "First Receive Time": first_time,
                "Last Receive Time": last_time,
                "Duration (s)": round(
                    duration_seconds,
                    2,
                ),
                "Packet Rate (packets/min)": round(
                    packet_rate_per_minute,
                    3,
                ),
            }
        )

    output_df = pd.DataFrame(results)

    output_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("Mesh analysis completed.")
    print(f"One-hour period: {PERIOD_LABEL}")
    print(output_df)
    print()
    print(f"Saved to: {OUTPUT_FILE}")

def main() -> int:
    try:
        analyse_mesh()
        return 0

    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1

    except Exception as error:
        print(
            "UNEXPECTED ERROR: "
            f"{type(error).__name__}: {error}"
        )
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
