"""
Simple BLE sniffer using bleak.

What it does:
- Reads target MACs from config.TARGET_MACS
- Filters advertisements to those targets
- Logs MAC, RSSI, and a high-resolution timestamp
- Enqueues each event into a thread-safe queue
- Writes events to a CSV file under data/runs/<run_timestamp>/
"""

# Standard library imports
import asyncio
import csv
import os
import time
from datetime import datetime
from queue import Queue

# Third-party import (install with: pip install bleak)
from bleak import BleakScanner

# Local configuration file
import config

# TODO: change EVENT_QUEUE to Asyncio.Queue if we want to use it within async code instead of threads

# Thread-safe queue for sharing BLE events with other parts of the program
EVENT_QUEUE = Queue()

# Base directory of this script (so paths work no matter where you run from)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def ensure_output_folder() -> str:
    """Create a run folder and return the CSV file path."""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = os.path.join(BASE_DIR, "data", "runs", run_timestamp)
    os.makedirs(run_folder, exist_ok=True)
    csv_path = os.path.join(run_folder, f"ble_events_{run_timestamp}.csv")
    return csv_path


async def scan_loop():
    """Continuously scan for BLE advertisements and log target devices."""
    csv_path = ensure_output_folder()

    # Prepare CSV file and write header
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_ns", "mac", "rssi", "name"])  # Header row

        # Normalize target MACs to lowercase for comparisons
        target_macs = {m.lower() for m in getattr(config, "TARGET_MACS", [])}

        if not target_macs:
            print("No target MACs found in config.TARGET_MACS. Nothing to scan for.")

        def detection_callback(device, advertisement_data):
            """Handle each advertisement packet."""
            try:
                # Read and normalize the MAC address
                mac = (device.address or "").lower()

                # Only process devices in the target list
                if mac in target_macs:
                    # High-resolution timestamp (nanoseconds)
                    timestamp_ns = time.time_ns()
                    rssi = advertisement_data.rssi
                    device_name = device.name or "Unknown"

                    # Log to console
                    print(f"Time Stamp (ns): {timestamp_ns} | MAC:{mac} | RSSI: {rssi} | Name: {device_name}")

                    # Enqueue event for other threads/processes
                    EVENT_QUEUE.put({
                        "timestamp_ns": timestamp_ns,
                        "mac": mac,
                        "rssi": rssi,
                        "name": device_name
                    })

                    # Write to CSV
                    writer.writerow([timestamp_ns, mac, rssi, device_name])
                    f.flush()
            except Exception as exc:
                # Keep scanning even if one packet causes an issue
                print(f"Error processing advertisement: {exc}")

        # Create and start the BLE scanner
        scanner = BleakScanner(detection_callback)
        try:
            await scanner.start()
            print("BLE scanning started. Press Ctrl+C to stop.")

            # Run forever (until Ctrl+C)
            while True:
                await asyncio.sleep(1)
        except Exception as exc:
            # Basic error handling in case the BLE adapter fails
            print(f"BLE scanning error: {exc}")
        finally:
            # Try to stop the scanner cleanly
            try:
                await scanner.stop()
            except Exception:
                pass


def main():
    """Entry point to run the async scan loop."""
    try:
        asyncio.run(scan_loop())
    except KeyboardInterrupt:
        print("Scanning stopped by user.")
    except Exception as exc:
        print(f"Unexpected error: {exc}")


main()
