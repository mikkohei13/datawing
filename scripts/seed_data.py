#!/usr/bin/env python3
"""Seed sample species sighting data into ClickHouse."""

import os
from datetime import datetime
from pathlib import Path

import clickhouse_connect

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")

MAX_ROWS = 10000
DATA_FILE = Path(__file__).parent.parent / "data" / "mlk-public-data-10k.txt"

# Column indices from the TSV file
COL_SPECIES = 0
COL_RESULT_ID = 5
COL_TIME = 10
COL_LAT = 17
COL_LON = 18


def parse_timestamp(time_str: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    # Handle format like '2025-05-16T11:43:27.235000'
    return datetime.fromisoformat(time_str)


def load_data_from_file(filepath: Path, max_rows: int) -> list:
    """Load species sighting data from a TSV file.

    Reads line-by-line for efficiency with large files.
    Skips rows where species, lat, lon, result_id, or time is empty.

    Args:
        filepath: Path to the TSV data file.
        max_rows: Maximum number of valid rows to load.

    Returns:
        List of tuples (id, species, time, lat, lon) where id is from result_id column.
    """
    data = []
    with open(filepath, "r") as f:
        # Skip header line
        next(f)
        for line in f:
            if len(data) >= max_rows:
                break

            fields = line.rstrip("\n").split("\t")

            # Extract required fields
            species = fields[COL_SPECIES] if len(fields) > COL_SPECIES else ""
            result_id = fields[COL_RESULT_ID] if len(fields) > COL_RESULT_ID else ""
            time_str = fields[COL_TIME] if len(fields) > COL_TIME else ""
            lat = fields[COL_LAT] if len(fields) > COL_LAT else ""
            lon = fields[COL_LON] if len(fields) > COL_LON else ""

            # Skip row if any required field is empty
            if not species or not result_id or not time_str or not lat or not lon:
                continue

            data.append((
                result_id,
                species,
                parse_timestamp(time_str),
                float(lat),
                float(lon),
            ))

    return data


TABLE_NAME = "species_sightings"


def table_exists(client, table_name: str) -> bool:
    """Check if a table exists in ClickHouse."""
    result = client.command(f"EXISTS TABLE {table_name}")
    return result == 1


def create_table(client):
    """Create the species_sightings table."""
    client.command(f"""
        CREATE TABLE {TABLE_NAME} (
            id String,
            species_name String,
            time DateTime64(3),
            latitude Float64,
            longitude Float64
        ) ENGINE = MergeTree()
        ORDER BY (time, id)
    """)


def main():
    client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST)

    # Check if table exists and ask for confirmation to recreate
    if table_exists(client, TABLE_NAME):
        response = input(
            f"Table '{TABLE_NAME}' already exists. Drop and recreate? [y/N]: "
        )
        if response.lower() != "y":
            print("Aborted.")
            return
        client.command(f"DROP TABLE {TABLE_NAME}")
        print(f"Dropped table '{TABLE_NAME}'.")

    create_table(client)
    print(f"Created table '{TABLE_NAME}'.")

    # Load data from file
    data = load_data_from_file(DATA_FILE, MAX_ROWS)

    # Insert data
    client.insert(
        TABLE_NAME,
        data,
        column_names=["id", "species_name", "time", "latitude", "longitude"],
    )

    print(f"Inserted {len(data)} species sightings")


if __name__ == "__main__":
    main()
