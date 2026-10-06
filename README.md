# ENG402 Microclimate Monitoring

ESP32 sensing nodes, a USB root node and a Raspberry Pi gateway.

## Files

| Folder | Contents |
| --- | --- |
| `firmware/` | Sensor and root Arduino projects |
| `code/` | Acquisition, processing, sequence analysis and plots |
| `dashboard/` | Flask dashboard and HTML template |
| `config/` | Node configuration |
| `systemd/` | Services, timers and a path watcher |
| `deployment/` | USB backup script |
| `analysis/` | MATLAB plots and thesis figure generation |
| `environment/` | Raspberry Pi export records |
| `data/relay/` | CSV export of the 906 supplied relay records |

## Firmware

Open `SensorNode.ino` and `RootNode.ino` as separate Arduino projects.
Use the DFRobot FireBeetle ESP32 board and install painlessMesh and
Adafruit BMP280 Library with their dependencies.

Set `SENSOR_NAME` to `Sensor_A`, `Sensor_B`, `Sensor_C` or `Sensor_D` before
uploading each sensor. Replace `YOUR_MESH_PASSWORD` in both projects with
the same password. All nodes use the same mesh prefix, password and port.
The serial baud rate is 115200. The BMP280 uses SDA 21 and SCL 22.

## Raspberry Pi

Install the packages listed in `requirements.txt` for the Python interpreter
used by the services. This export uses `/usr/bin/python3`.

The service files use `/home/pi/eng402_gateway_data/` for `code`, `dashboard`
and `config`, `/home/pi/sync_eng402.sh` for the backup script, and
`/mnt/eng402_usb` for the USB drive. Copy the folders and script to these
locations, or update the paths for your own setup. The backup needs `rsync`.
Check the serial device in `code/gateway.py` and the USB mount before use.

Service files belong in `/etc/systemd/system/`. After copying them, run:

```bash
mkdir -p /home/pi/eng402_gateway_data/{raw,status,processed,figures,logs,errors}
sudo chmod +x /home/pi/sync_eng402.sh
sudo systemctl daemon-reload
sudo systemctl enable --now eng402-gateway.service eng402-dashboard.service
sudo systemctl enable --now eng402-processing.timer eng402-sync.timer eng402-data-watch.path
```

The exported Pi used Python 3.13.5 on Raspbian 13. Full environment records
are in `environment/`; `requirements.txt` lists direct Python dependencies.

## Analysis

Run the MATLAB files from `analysis/matlab/` and select the requested CSV files.

| MATLAB file | Plot |
| --- | --- |
| `plot_sensor_temperature.m` | Temperature |
| `plot_sensor_pressure.m` | Pressure |
| `plot_ABCD_runtime_19_20Sep.m` | Four-node reception, 19 Sep 22:56 to 20 Sep 11:00 |
| `plot_multihop.m` | Relay experiment |
| `plot_offline_operation.m` | Offline gateway operation |
| `plot_figure.m` | Cold-event records |
| `plot_gateway_recovery.m` | USB serial recovery |

The 11:00 timeline is a separate display window. The main experiment and
battery analysis end at 20 September 2026, 09:42:37. The battery test used
charged 3.7 V, 2600 mAh cells on Node C and Node D, with continuous power
on Node A and Node B.

For the existing Python thesis figures, place the selected daily inputs
`sensor_data_2026-09-14.csv` through `sensor_data_2026-09-20.csv` in `data/main/`:

```bash
mkdir -p figures
python3 analysis/python/regenerate_figures.py --input-dir data/main --output-dir figures
```

These inputs must be the selected thesis records; the 14 September input
contains 17,809 records. The large daily files and operational test records
are kept in the separate data archive. The Python drawing routines retain
the earlier diagrams, including the battery-test wiring; use the separately
revised diagrams in the final thesis.

## Checksums

```bash
python3 verify_manifest.py
```

After changing files, create a new manifest with:

```bash
python3 make_manifest.py .
```

Comments were removed or shortened. Executable logic, protocol fields and
log messages were preserved; the mesh password is an example placeholder.
Python syntax and code equivalence checks passed, as did shell syntax and
package checksums. MATLAB and Arduino were not executed on hardware here.
