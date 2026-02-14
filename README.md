# Datawing

System to visualize large-scale biodiversity occurrence data. Proof of concept, work in progress.

## Overview

**Tech stack:** Flask, ClickHouse, pydeck (deck.gl), Docker Compose.

**Architecture:** Server-heavy, client-light, modular. The Flask backend does all querying, aggregation, and visualization generation. Analysis and visualization modules live in `app/modules/` and are discovered automatically at startup. The browser receives a fully rendered page with no AJAX calls or client-side frameworks. User interactions (filtering, changing settings) trigger full page reloads via GET query parameters.

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

Open http://localhost:5001/ in your browser.

More data is available at http://tun.fi/HR.6578

## Creating modules

The app is organized as a set of modules under `app/modules/`. Each module is a directory with a `module.py` and an optional `templates/` subdirectory. Modules are discovered automatically at startup — no registration needed.

### File structure

    app/modules/my_module/
      module.py
      templates/
        view.html          # optional

### module.py contract

Define `TITLE`, `DESCRIPTION`, and a `render(ctx)` function:

```python
from core import format_tooltip  # shared helpers in app/core.py

TITLE = "My Module"
DESCRIPTION = "Short description shown on the home page"

def render(ctx):
    # ctx.db              — ClickHouse client (clickhouse-connect)
    # ctx.request         — Flask request object (query params via ctx.request.args)
    # ctx.species_list()  — returns (all_species_sorted, species_counts) tuple
    # ctx.parse_map_controls() — returns (point_size, scale_with_map) from request
    # ctx.render_map(data, scale_with_map, point_size) — builds pydeck map HTML
    # ctx.render_template(name, **kwargs) — renders templates/<name> within base.html

    result = ctx.db.query("SELECT ... FROM species_sightings WHERE ...")
    # ... process data ...
    return ctx.render_template("view.html", data=data)
```

The route is derived from the directory name (`my_module` becomes `/my_module`).

### Templates

Templates use Jinja2 and extend `base.html` (which provides the nav bar). Shared partials are available via `{% include %}`:

- `partials/map_controls.html` — scale-with-map toggle + point size slider (expects `scale_with_map` and `point_size` in context)
- `partials/species_selector.html` — species radio list (expects `all_species`, `selected_species`, `species_counts`)

### Data access

Modules query the `species_sightings` ClickHouse table directly via `ctx.db`. The table schema:

    species_name String, time DateTime64(3), latitude Float64, longitude Float64,
    day_of_year Int32, year Int32

See existing modules in `app/modules/` for working examples.

## Development principles

- This is a one-person development project, not a production system. Do not aim for production-grade architecture; instead, favor simple solutions (KISS).
- Avoid over-engineering and premature optimization. Focus on solving the actual problem rather than hypothetical future needs.
- Keep the architecture simple and understandable for AI-assisted programming tools.
- Use clear comments to explain why something is done rather than what is done; make the code self-documenting where possible.

## License

Code is licensed under the MIT License.

Sample data in ./data is licensed under Creative Commons Attribution 4.0 International License. Citation:

    Finnish Muuttolintujen kevät -data, University of Jyväskylä. http://tun.fi/HR.6578 Creative Commons Attribution 4.0 International https://creativecommons.org/licenses/by/4.0/