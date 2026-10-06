#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path("/home/pi/eng402_gateway_data")
USB_LOG_FILE = BASE_DIR / "logs" / "usb_sync.log"

EXPECTED_NODES = 4
ONLINE_TIMEOUT_SECONDS = 360
USB_WARNING_MINUTES = 10

def safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def calculate_packet_statistics(
    df: pd.DataFrame,
) -> dict:

    if df.empty:
        return {
            "average_packet_rate": 0.0,
            "packet_loss_percent": 0.0,
            "packets_received": 0,
            "missing_packets": 0,
        }

    required = {
        "sensor_name",
        "receive_time",
        "sequence",
    }

    if not required.issubset(df.columns):
        return {
            "average_packet_rate": 0.0,
            "packet_loss_percent": 0.0,
            "packets_received": len(df),
            "missing_packets": 0,
        }

    working = df.copy()

    working["receive_time"] = pd.to_datetime(
        working["receive_time"],
        errors="coerce",
    )

    working["sequence"] = pd.to_numeric(
        working["sequence"],
        errors="coerce",
    )

    working = working.dropna(
        subset=[
            "sensor_name",
            "receive_time",
            "sequence",
        ]
    )

    total_received = 0
    total_missing = 0
    rates = []

    for _, group in working.groupby("sensor_name"):
        group = group.sort_values("receive_time")

        packet_count = len(group)
        total_received += packet_count

        duration_seconds = (
            group["receive_time"].max()
            - group["receive_time"].min()
        ).total_seconds()

        if duration_seconds > 0:
            rate = packet_count / (duration_seconds / 60)
            rates.append(rate)

        unique_sequences = (
            group["sequence"]
            .dropna()
            .astype(int)
            .drop_duplicates()
            .sort_values()
        )

        if len(unique_sequences) >= 2:
            differences = unique_sequences.diff().dropna()

            valid_gaps = differences[
                (differences > 1)
                & (differences <= 100)
            ]

            missing = int(
                valid_gaps.sub(1).sum()
            )

            total_missing += max(missing, 0)

    expected_packets = total_received + total_missing

    if expected_packets > 0:
        packet_loss_percent = (
            total_missing / expected_packets
        ) * 100
    else:
        packet_loss_percent = 0.0

    average_rate = (
        sum(rates) / len(rates)
        if rates
        else 0.0
    )

    return {
        "average_packet_rate": round(average_rate, 3),
        "packet_loss_percent": round(
            packet_loss_percent,
            3,
        ),
        "packets_received": int(total_received),
        "missing_packets": int(total_missing),
    }

def calculate_node_status(
    df: pd.DataFrame,
) -> dict:

    if (
        df.empty
        or "sensor_name" not in df.columns
        or "receive_time" not in df.columns
    ):
        return {
            "connected_nodes": 0,
            "total_nodes": EXPECTED_NODES,
            "latest_data_age_seconds": None,
            "node_statuses": [],
        }

    working = df.copy()

    working["receive_time"] = pd.to_datetime(
        working["receive_time"],
        errors="coerce",
    )

    working = working.dropna(
        subset=["sensor_name", "receive_time"]
    )

    if working.empty:
        return {
            "connected_nodes": 0,
            "total_nodes": EXPECTED_NODES,
            "latest_data_age_seconds": None,
            "node_statuses": [],
        }

    now = pd.Timestamp.now()

    latest_rows = (
        working.sort_values("receive_time")
        .groupby("sensor_name")
        .tail(1)
        .sort_values("sensor_name")
    )

    statuses = []
    connected_nodes = 0

    for _, row in latest_rows.iterrows():
        data_age = (
            now - row["receive_time"]
        ).total_seconds()

        data_age = max(data_age, 0.0)

        online = data_age <= ONLINE_TIMEOUT_SECONDS

        if online:
            connected_nodes += 1

        if not online:
            quality_percent = 0
            quality_level = "critical"
        elif data_age <= 120:
            quality_percent = 100
            quality_level = "healthy"
        elif data_age <= 240:
            quality_percent = 80
            quality_level = "healthy"
        else:
            quality_percent = 60
            quality_level = "warning"

        statuses.append(
            {
                "sensor_name": row["sensor_name"],
                "online": online,
                "data_age_seconds": round(
                    data_age,
                    1,
                ),
                "quality_percent": quality_percent,
                "quality_level": quality_level,
            }
        )

    latest_time = working["receive_time"].max()

    latest_age = max(
        (now - latest_time).total_seconds(),
        0.0,
    )

    return {
        "connected_nodes": connected_nodes,
        "total_nodes": EXPECTED_NODES,
        "latest_data_age_seconds": round(
            latest_age,
            1,
        ),
        "node_statuses": statuses,
    }

def read_usb_backup_status() -> dict:

    if not USB_LOG_FILE.exists():
        return {
            "status": "Unavailable",
            "level": "warning",
            "last_sync": None,
            "age_minutes": None,
            "message": "USB sync log not found",
        }

    try:
        lines = USB_LOG_FILE.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    except OSError:
        return {
            "status": "Unavailable",
            "level": "warning",
            "last_sync": None,
            "age_minutes": None,
            "message": "USB sync log cannot be read",
        }

    non_empty_lines = [
        line.strip()
        for line in lines
        if line.strip()
    ]

    if not non_empty_lines:
        return {
            "status": "Unavailable",
            "level": "warning",
            "last_sync": None,
            "age_minutes": None,
            "message": "USB sync log is empty",
        }

    last_line = non_empty_lines[-1]

    try:
        timestamp_text = last_line[:19]

        last_sync = datetime.strptime(
            timestamp_text,
            "%Y-%m-%d %H:%M:%S",
        )

        age_minutes = max(
            (
                datetime.now() - last_sync
            ).total_seconds() / 60,
            0.0,
        )

    except ValueError:
        return {
            "status": "Unknown",
            "level": "warning",
            "last_sync": None,
            "age_minutes": None,
            "message": last_line,
        }

    if "Sync completed" in last_line:
        if age_minutes <= USB_WARNING_MINUTES:
            status = "Synced"
            level = "healthy"
        else:
            status = "Delayed"
            level = "warning"

    elif "not mounted" in last_line:
        status = "Not mounted"
        level = "critical"

    else:
        status = "Warning"
        level = "warning"

    return {
        "status": status,
        "level": level,
        "last_sync": last_sync.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "age_minutes": round(age_minutes, 1),
        "message": last_line,
    }

def determine_gateway_health(
    node_status: dict,
    packet_statistics: dict,
) -> dict:

    connected = node_status["connected_nodes"]
    latest_age = node_status[
        "latest_data_age_seconds"
    ]

    packet_loss = packet_statistics[
        "packet_loss_percent"
    ]

    if (
        connected == EXPECTED_NODES
        and latest_age is not None
        and latest_age <= ONLINE_TIMEOUT_SECONDS
        and packet_loss < 5
    ):
        return {
            "status": "Healthy",
            "level": "healthy",
            "message": "All nodes are communicating normally",
        }

    if (
        connected >= EXPECTED_NODES - 1
        and latest_age is not None
        and latest_age <= 60
        and packet_loss < 15
    ):
        return {
            "status": "Warning",
            "level": "warning",
            "message": "Minor communication issue detected",
        }

    return {
        "status": "Critical",
        "level": "critical",
        "message": "Gateway or Mesh communication problem",
    }

def build_health_report(
    df: pd.DataFrame,
) -> dict:

    node_status = calculate_node_status(df)
    packet_statistics = calculate_packet_statistics(df)

    gateway_health = determine_gateway_health(
        node_status,
        packet_statistics,
    )

    usb_status = read_usb_backup_status()

    return {
        "gateway": gateway_health,
        "nodes": node_status,
        "packets": packet_statistics,
        "usb": usb_status,
    }
