import json
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


@app.route("/")
def index():
    client = get_client()

    # Check if table exists and has data
    try:
        result = client.query(
            "SELECT species_name, latitude, longitude FROM species_sightings"
        )
        data = [
            {"species_name": row[0], "latitude": row[1], "longitude": row[2]}
            for row in result.result_rows
        ]
    except Exception:
        data = []

    if not data:
        return """
        <h1>No data yet!</h1>
        <p>Run the seed script to populate data:</p>
        <pre>docker compose exec app python scripts/seed_data.py</pre>
        """

    # Get unique species for filter
    all_species = sorted(set(d["species_name"] for d in data))

    # Get selected species from query params (default to all)
    selected_species = request.args.getlist("species")
    if not selected_species:
        selected_species = all_species

    # Filter data by selected species
    filtered_data = [d for d in data if d["species_name"] in selected_species]

    # Create pydeck visualization
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=filtered_data,
        get_position=["longitude", "latitude"],
        get_radius=50000,
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
        tooltip={"text": "{species_name}"},
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
        result_count=len(filtered_data),
        species_counts=species_counts,
    )
