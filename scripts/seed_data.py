#!/usr/bin/env python3
"""Seed sample species sighting data into ClickHouse."""

import os
import random

import clickhouse_connect

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")

SPECIES = [
    "Arctic Fox",
    "Bengal Tiger",
    "Blue Whale",
    "Emperor Penguin",
    "Giant Panda",
    "Golden Eagle",
    "Green Sea Turtle",
    "Grizzly Bear",
    "Humpback Whale",
    "Komodo Dragon",
    "Mountain Gorilla",
    "Polar Bear",
    "Red Kangaroo",
    "Snow Leopard",
    "African Elephant",
]


def main():
    client = clickhouse_connect.get_client(host=CLICKHOUSE_HOST)

    # Create table
    client.command("""
        CREATE TABLE IF NOT EXISTS species_sightings (
            id UInt32,
            species_name String,
            latitude Float64,
            longitude Float64
        ) ENGINE = MergeTree()
        ORDER BY id
    """)

    # Generate random sightings
    data = []
    for i in range(100):
        data.append(
            (
                i + 1,
                random.choice(SPECIES),
                random.uniform(-60, 70),  # latitude
                random.uniform(-180, 180),  # longitude
            )
        )

    # Clear existing data and insert new
    client.command("TRUNCATE TABLE species_sightings")
    client.insert(
        "species_sightings",
        data,
        column_names=["id", "species_name", "latitude", "longitude"],
    )

    print(f"Inserted {len(data)} species sightings")


if __name__ == "__main__":
    main()
