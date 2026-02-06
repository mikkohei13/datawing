# Datawing

System to visualize large-scale biodiversity occurrence data. Proof of concept, work in progress.

## Overview

**Tech stack:** Flask, ClickHouse, pydeck (deck.gl), Docker Compose.

**Data flow:**
1. Seed script inserts species occurrence records (name, lat, lon) into ClickHouse
2. Flask queries ClickHouse for all sightings
3. pydeck renders sightings on a world map
4. Map is served as self-contained HTML with embedded deck.gl

## Run

    docker compose up --build

Open http://localhost:5000/ in your browser.

## Seed data

    docker compose exec app python scripts/seed_data.py

## Development principles

- This is a one-person development project, not a production system. Do not aim for production-grade architecture; instead, favor simple solutions (KISS).
- Avoid over-engineering and premature optimization. Focus on solving the actual problem rather than hypothetical future needs.
- Keep the architecture simple and understandable for AI-assisted programming tools.
- Use clear comments to explain why something is done rather than what is done; make the code self-documenting where possible.
