import json
import math
import os
from pathlib import Path

import clickhouse_connect
import pydeck as pdk
from flask import Flask, render_template, request

app = Flask(__name__)

SPECIES_COUNTS_CACHE = Path(__file__).parent / "species_counts_cache.json"


def load_species_counts():
    """Load species counts from cache file."""
    if SPECIES_COUNTS_CACHE.exists():
        with open(SPECIES_COUNTS_CACHE) as f:
            return json.load(f)
    return {}

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")


def get_client():
    return clickhouse_connect.get_client(host=CLICKHOUSE_HOST)


def format_tooltip(count, species_list, earliest, latest):
    """Build a tooltip string for an aggregated grid cell."""
    n_species = len(species_list)
    header = f"{count} records | {n_species} species"
    species_str = ", ".join(sorted(species_list))
    date_str = f"{earliest.strftime('%Y-%m-%d')} — {latest.strftime('%Y-%m-%d')}"
    return f"{header}\n{species_str}\n{date_str}"


@app.route("/")
def index():
    client = get_client()

    # Get species list for the sidebar filter
    try:
        species_result = client.query(
            "SELECT DISTINCT species_name FROM species_sightings ORDER BY species_name"
        )
        all_species = [row[0] for row in species_result.result_rows]
    except Exception:
        all_species = sorted(load_species_counts().keys())

    if not all_species:
        return """
        <h1>No data yet!</h1>
        <p>Run the seed script to populate data:</p>
        <pre>docker compose exec app python scripts/seed_data.py</pre>
        """

    # Get selected species from query params (default to all)
    selected_species = request.args.getlist("species")
    if not selected_species:
        selected_species = all_species

    # Aggregation query: one row per grid cell with count, species list, date range.
    # Push species filter into WHERE clause so ClickHouse does the filtering.
    filtering = len(selected_species) < len(all_species)
    if filtering:
        placeholders = ", ".join(["%s"] * len(selected_species))
        query = f"""
            SELECT
                latitude,
                longitude,
                COUNT(*) AS count,
                groupUniqArray(species_name) AS species,
                min(time) AS earliest,
                max(time) AS latest
            FROM species_sightings
            WHERE species_name IN ({placeholders})
            GROUP BY latitude, longitude
        """
        result = client.query(query, parameters=selected_species)
    else:
        result = client.query("""
            SELECT
                latitude,
                longitude,
                COUNT(*) AS count,
                groupUniqArray(species_name) AS species,
                min(time) AS earliest,
                max(time) AS latest
            FROM species_sightings
            GROUP BY latitude, longitude
        """)

    # Build pydeck data from aggregated rows
    total_records = 0
    data = []
    for row in result.result_rows:
        lat, lon, count, species_list, earliest, latest = row
        total_records += count
        data.append({
            "latitude": lat,
            "longitude": lon,
            "count": count,
            "tooltip": format_tooltip(count, species_list, earliest, latest),
            # Scale radius by sqrt(count) so area is proportional to count
            "radius": 1000 * math.sqrt(count),
        })

    # Create pydeck visualization
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position=["longitude", "latitude"],
        get_radius="radius",
        get_fill_color=[255, 140, 0, 200],
        pickable=True,
        radius_min_pixels=3,
        radius_max_pixels=15,
    )

    view_state = pdk.ViewState(
        latitude=65.062,
        longitude=26.719,
        zoom=5,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{tooltip}"},
    )

    map_html = deck.to_html(as_string=True)

    # Inject dark background to prevent white flash inside iframe
    dark_bg_style = "<style>html, body { background: #121212 !important; }</style>"
    map_html = map_html.replace("<head>", f"<head>{dark_bg_style}", 1)

    species_counts = load_species_counts()

    return render_template(
        "index.html",
        map_html=map_html,
        all_species=all_species,
        selected_species=selected_species,
        result_count=total_records,
        species_counts=species_counts,
    )
