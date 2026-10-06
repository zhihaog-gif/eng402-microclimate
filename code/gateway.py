#!/usr/bin/env python3

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path

import serial
from serial import SerialException

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1
RECONNECT_DELAY_SECONDS = 3

BASE_DIRECTORY = Path.home() / "eng402_gateway_data"
RAW_DATA_DIRECTORY = BASE_DIRECTORY / "raw"
STATUS_DIRECTORY = BASE_DIRECTORY / "status"
ERROR_DIRECTORY = BASE_DIRECTORY / "errors"

SENSOR_FIELDS = [
    "receive_time",
    "receive_date",
    "receive_timestamp_ms",
    "type",
    "sensor_name",
    "node_id",
    "sequence",
    "mesh_time_us",
    "uptime_ms",
    "bmp280_connected",
    "temperature_c",
    "humidity_percent",
    "pressure_hpa",
    "error",
    "raw_json",
]

STATUS_FIELDS = [
    "receive_time",
    "event",
    "root_node_id",
    "node_id",
    "connected_nodes",
    "mesh_time_us",
    "uptime_ms",
    "raw_json",
]

ERROR_FIELDS = [
    "receive_time",
    "error_type",
    "raw_line",
]

def create_directories() -> None:

    RAW_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    STATUS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    ERROR_DIRECTORY.mkdir(parents=True, exist_ok=True)

def current_date_string() -> str:

    return datetime.now().strftime("%Y-%m-%d")

def append_csv_row(
    file_path: Path,
    fieldnames: list[str],
    row: dict,
) -> None:

    file_exists = file_path.exists()
    file_is_empty = not file_exists or file_path.stat().st_size == 0

    with file_path.open(
        mode="a",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        if file_is_empty:
            writer.writeheader()

        writer.writerow(row)
        csv_file.flush()
        os.fsync(csv_file.fileno())

def save_sensor_data(data: dict, raw_json: str) -> None:

    now = datetime.now()

    row = {
        "receive_time": now.isoformat(timespec="milliseconds"),
        "receive_date": now.strftime("%Y-%m-%d"),
        "receive_timestamp_ms": int(now.timestamp() * 1000),
        "type": data.get("type", ""),
        "sensor_name": data.get("sensor_name", ""),
        "node_id": data.get("node_id", ""),
        "sequence": data.get("sequence", ""),
        "mesh_time_us": data.get("mesh_time_us", ""),
        "uptime_ms": data.get("uptime_ms", ""),
        "bmp280_connected": data.get("bmp280_connected", ""),
        "temperature_c": data.get("temperature_c", ""),
        "humidity_percent": data.get(
            "humidity_percent",
            data.get("humidity", ""),
        ),
        "pressure_hpa": data.get("pressure_hpa", ""),
        "error": data.get("error", ""),
        "raw_json": raw_json,
    }

    output_file = (
        RAW_DATA_DIRECTORY
        / f"sensor_data_{current_date_string()}.csv"
    )

    append_csv_row(output_file, SENSOR_FIELDS, row)

def save_status_data(data: dict, raw_json: str) -> None:

    now = datetime.now()

    row = {
        "receive_time": now.isoformat(timespec="milliseconds"),
        "event": data.get("event", ""),
        "root_node_id": data.get("root_node_id", ""),
        "node_id": data.get("node_id", ""),
        "connected_nodes": data.get("connected_nodes", ""),
        "mesh_time_us": data.get("mesh_time_us", ""),
        "uptime_ms": data.get("uptime_ms", ""),
        "raw_json": raw_json,
    }

    output_file = (
        STATUS_DIRECTORY
        / f"mesh_status_{current_date_string()}.csv"
    )

    append_csv_row(output_file, STATUS_FIELDS, row)

def save_error(error_type: str, raw_line: str) -> None:

    row = {
        "receive_time": datetime.now().isoformat(
            timespec="milliseconds"
        ),
        "error_type": error_type,
        "raw_line": raw_line,
    }

    output_file = (
        ERROR_DIRECTORY
        / f"gateway_errors_{current_date_string()}.csv"
    )

    append_csv_row(output_file, ERROR_FIELDS, row)

def process_serial_line(line: str) -> None:

    if line.startswith("DATA:"):
        prefix = "DATA:"
        message_type = "DATA"

    elif line.startswith("STATUS:"):
        prefix = "STATUS:"
        message_type = "STATUS"

    else:
        save_error("unknown_prefix", line)
        print(f"[IGNORED] {line}")
        return

    raw_json = line[len(prefix):].strip()

    try:
        data = json.loads(raw_json)

    except json.JSONDecodeError as error:
        save_error(
            f"invalid_json: {error}",
            line,
        )
        print(f"[INVALID JSON] {line}")
        return

    if message_type == "DATA":
        save_sensor_data(data, raw_json)

        sensor_name = data.get("sensor_name", "Unknown")
        sequence = data.get("sequence", "")
        temperature = data.get("temperature_c")
        pressure = data.get("pressure_hpa")
        sensor_connected = data.get("bmp280_connected")

        print(
            f"[DATA] {sensor_name} | "
            f"sequence={sequence} | "
            f"BMP280={sensor_connected} | "
            f"temperature={temperature} C | "
            f"pressure={pressure} hPa"
        )

    else:
        save_status_data(data, raw_json)

        event = data.get("event", "Unknown")
        connected_nodes = data.get("connected_nodes", "")

        print(
            f"[STATUS] event={event} | "
            f"connected_nodes={connected_nodes}"
        )

def open_serial_connection() -> serial.Serial:

    connection = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        timeout=SERIAL_TIMEOUT,
    )

    time.sleep(2)
    connection.reset_input_buffer()

    return connection

def run_gateway() -> None:

    create_directories()

    print("=" * 60)
    print("ENG402 Raspberry Pi Gateway")
    print(f"Serial port: {SERIAL_PORT}")
    print(f"Baud rate: {BAUD_RATE}")
    print(f"Data directory: {BASE_DIRECTORY}")
    print("Press Ctrl+C to stop safely.")
    print("=" * 60)

    while True:
        serial_connection = None

        try:
            print(f"[CONNECTING] Opening {SERIAL_PORT}...")
            serial_connection = open_serial_connection()
            print("[CONNECTED] Root ESP32 serial connection established.")

            while True:
                raw_bytes = serial_connection.readline()

                if not raw_bytes:
                    continue

                line = raw_bytes.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if line:
                    process_serial_line(line)

        except SerialException as error:
            print(f"[SERIAL ERROR] {error}")
            print(
                f"[RETRY] Reconnecting in "
                f"{RECONNECT_DELAY_SECONDS} seconds..."
            )
            time.sleep(RECONNECT_DELAY_SECONDS)

        except OSError as error:
            print(f"[FILE ERROR] {error}")
            save_error("file_error", str(error))
            time.sleep(RECONNECT_DELAY_SECONDS)

        except KeyboardInterrupt:
            print("\n[STOPPING] Gateway stopped safely.")
            break

        except Exception as error:
            print(f"[UNEXPECTED ERROR] {error}")
            save_error("unexpected_error", str(error))
            time.sleep(RECONNECT_DELAY_SECONDS)

        finally:
            if (
                serial_connection is not None
                and serial_connection.is_open
            ):
                serial_connection.close()

if __name__ == "__main__":
    run_gateway()
