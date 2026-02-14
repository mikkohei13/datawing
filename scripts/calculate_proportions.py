#!/usr/bin/env python3
"""Calculate the proportion of each species compared to all data."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

MAX_ROWS = 10000000
START_YEAR = 2025
END_YEAR = 2025
PREDICTION_THRESHOLD = 0.8

DATA_FILE = Path(__file__).parent.parent / "data" / "mlk-public-data.txt"
OUTPUT_FILE = Path(__file__).parent.parent / "app" / "species_proportions.json"

# Column indices from the TSV file
COL_SPECIES = 0
COL_PREDICTION = 1
COL_TIME = 10


def count_species(filepath: Path, max_rows: int) -> Counter:
    """Count occurrences of each species from the TSV file.

    Applies the same year and prediction threshold filters as seed_data.py.
    """
    counts = Counter()
    total_valid = 0

    with open(filepath, "r") as f:
        # Skip header line
        next(f)
        for line in f:
            if total_valid >= max_rows:
                break

            fields = line.rstrip("\n").split("\t")

            # Filter by prediction threshold
            if len(fields) <= COL_PREDICTION:
                continue
            try:
                prediction = float(fields[COL_PREDICTION])
            except (ValueError, TypeError):
                continue
            if prediction < PREDICTION_THRESHOLD:
                continue

            species = fields[COL_SPECIES] if len(fields) > COL_SPECIES else ""
            time_str = fields[COL_TIME] if len(fields) > COL_TIME else ""

            if not species or not time_str:
                continue

            ts = datetime.fromisoformat(time_str)

            # Filter by year range
            if ts.year < START_YEAR or ts.year > END_YEAR:
                continue

            counts[species] += 1
            total_valid += 1

    return counts


def main():
    print(f"Reading data from {DATA_FILE}...")
    print(f"Filtering by year range {START_YEAR}-{END_YEAR} and prediction threshold {PREDICTION_THRESHOLD}...")

    counts = count_species(DATA_FILE, MAX_ROWS)
    total = sum(counts.values())

    print(f"Found {total:,} records across {len(counts)} species.")

    proportions = {
        species: round(count / total, 4)
        for species, count in sorted(counts.items())
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(proportions, f, indent=2)

    print(f"Saved proportions to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
