#!/usr/bin/env python3
"""Seed sample species sighting data into ClickHouse."""

import json
import os
from datetime import datetime
from pathlib import Path

import clickhouse_connect

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")

MAX_ROWS = 10000000
START_YEAR = 2025
END_YEAR = 2025
PREDICTION_THRESHOLD = 0.8

BATCH_SIZE = 100000
DATA_FILE = Path(__file__).parent.parent / "data" / "mlk-public-data.txt"

# Column indices from the TSV file
COL_SPECIES = 0
COL_PREDICTION = 1
COL_RESULT_ID = 5
COL_TIME = 10
COL_LAT = 17
COL_LON = 18


def parse_timestamp(time_str: str) -> datetime:
    """Parse ISO 8601 timestamp string to datetime."""
    # Handle format like '2025-05-16T11:43:27.235000'
    return datetime.fromisoformat(time_str)


def iter_data_batches(filepath: Path, max_rows: int, batch_size: int):
    """Yield batches of species sighting data from a TSV file.

    Reads line-by-line and yields batches for memory-efficient processing.
    Skips rows where prediction < PREDICTION_THRESHOLD, species, lat, lon,
    result_id, or time is empty.

    Args:
        filepath: Path to the TSV data file.
        max_rows: Maximum number of valid rows to process.
        batch_size: Number of records per batch.

    Yields:
        Lists of tuples (id, species, time, lat, lon, day_of_year, year).
    """
    batch = []
    total_count = 0

    with open(filepath, "r") as f:
        # Skip header line
        next(f)
        for line in f:
            if total_count >= max_rows:
                break

            fields = line.rstrip("\n").split("\t")

            # Filter by prediction threshold (second column)
            if len(fields) <= COL_PREDICTION:
                continue
            try:
                prediction = float(fields[COL_PREDICTION])
            except (ValueError, TypeError):
                continue
            if prediction < PREDICTION_THRESHOLD:
                continue

            # Extract required fields
            species = fields[COL_SPECIES] if len(fields) > COL_SPECIES else ""
            result_id = fields[COL_RESULT_ID] if len(fields) > COL_RESULT_ID else ""
            time_str = fields[COL_TIME] if len(fields) > COL_TIME else ""
            lat = fields[COL_LAT] if len(fields) > COL_LAT else ""
            lon = fields[COL_LON] if len(fields) > COL_LON else ""

            # Skip row if any required field is empty
            if not species or not result_id or not time_str or not lat or not lon:
                continue

            ts = parse_timestamp(time_str)

            # Filter by year range
            if ts.year < START_YEAR or ts.year > END_YEAR:
                continue

            batch.append((
                result_id,
                species,
                ts,
                float(lat),
                float(lon),
                ts.timetuple().tm_yday,
                ts.year,
            ))
            total_count += 1

            if len(batch) >= batch_size:
                yield batch
                batch = []

    # Yield remaining records
    if batch:
        yield batch


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
            longitude Float64,
            day_of_year Int32,
            year Int32
        ) ENGINE = MergeTree()
        ORDER BY (species_name, latitude, longitude, time, id)
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

    print(f"Loading and inserting up to {MAX_ROWS:,} records from {DATA_FILE}...")
    print(f"Filtering by year range {START_YEAR}-{END_YEAR} and prediction threshold {PREDICTION_THRESHOLD}...")

    # Stream data in batches: read and insert each batch
    total_inserted = 0
    column_names = ["id", "species_name", "time", "latitude", "longitude", "day_of_year", "year"]

    for batch in iter_data_batches(DATA_FILE, MAX_ROWS, BATCH_SIZE):
        client.insert(TABLE_NAME, batch, column_names=column_names)
        total_inserted += len(batch)
        print(f"Inserted {total_inserted:,} records...")

    print(f"Done. Inserted {total_inserted:,} species sightings")

    # Update species counts cache
    update_species_counts_cache(client)


def update_species_counts_cache(client):
    """Query species counts and write to cache file."""
    result = client.query(
        f"SELECT species_name, COUNT(*) as count FROM {TABLE_NAME} GROUP BY species_name"
    )
    counts = {row[0]: row[1] for row in result.result_rows}

    cache_path = Path(__file__).parent.parent / "app" / "species_counts_cache.json"
    with open(cache_path, "w") as f:
        json.dump(counts, f)

    print(f"Updated species counts cache with {len(counts)} species")


if __name__ == "__main__":
    main()
