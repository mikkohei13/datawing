# Datawing

System to visualize large-scale biodiversity occurrence data. Proof of concept, work in progress.

## Overview

**Tech stack:** Flask, ClickHouse, pydeck (deck.gl), Docker Compose.

**Architecture:** Server-heavy, client-light. The Flask backend does all querying, aggregation, and visualization generation. The browser receives a fully rendered page with no AJAX calls or client-side frameworks. User interactions (filtering, changing settings) trigger full page reloads via GET query parameters.

**Data flow:**
1. A seed script reads source data (TSV) and batch-inserts occurrence records into ClickHouse
2. On each page load, Flask runs aggregation queries against ClickHouse (grouping by coordinates, filtering by species) and computes per-point colors, opacity, and tooltips
3. pydeck generates a self-contained HTML document with embedded deck.gl JavaScript and all point data as inline JSON
4. Flask embeds this map HTML into a Jinja2 template via an iframe (`srcdoc`), alongside server-rendered sidebar controls and charts
5. The map lives inside an iframe because pydeck produces a standalone page — the sidebar and map cannot communicate via DOM, which is why filter changes require a full reload

**Key implication:** All occurrence data for the current filter is baked into the page as inline JSON. There is no dynamic tile server or vector tile pipeline. This keeps the stack simple but means page size grows with the number of visible data points.

## Run

Start:

    docker compose up --build

Insert sample data:

    docker compose exec app python /scripts/seed_data.py

Open http://localhost:5000/ in your browser.

More data is available at http://tun.fi/HR.6578

## Development principles

- This is a one-person development project, not a production system. Do not aim for production-grade architecture; instead, favor simple solutions (KISS).
- Avoid over-engineering and premature optimization. Focus on solving the actual problem rather than hypothetical future needs.
- Keep the architecture simple and understandable for AI-assisted programming tools.
- Use clear comments to explain why something is done rather than what is done; make the code self-documenting where possible.

## License

Code is licensed under the MIT License.

Sample data in ./data is licensed under Creative Commons Attribution 4.0 International License. Citation:

    Finnish Muuttolintujen kevät -data, University of Jyväskylä. http://tun.fi/HR.6578 Creative Commons Attribution 4.0 International https://creativecommons.org/licenses/by/4.0/