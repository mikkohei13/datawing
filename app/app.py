import colorsys
import json
import math
import os
from pathlib import Path

import clickhouse_connect
import pydeck as pdk
from flask import Flask, render_template, request

app = Flask(__name__)

# Golden ratio conjugate for optimal hue distribution
GOLDEN_RATIO_CONJUGATE = 0.618033988749895


def generate_species_colors(species_list):
    """Generate distinct colors for each species using golden ratio hue distribution.
    
    Returns a dict mapping species name to RGB tuple (r, g, b).
    Colors are bright and visible against dark backgrounds.
    """
    colors = {}
    hue = 0.0
    for species in sorted(species_list):
        # Use high saturation and lightness for visibility on dark background
        r, g, b = colorsys.hls_to_rgb(hue, 0.6, 0.9)
        colors[species] = (int(r * 255), int(g * 255), int(b * 255))
        hue = (hue + GOLDEN_RATIO_CONJUGATE) % 1.0
    return colors

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

    # Get opacity setting from query params (default to 0.5)
    try:
        base_opacity = float(request.args.get("opacity", 0.5))
        base_opacity = max(0.0, min(1.0, base_opacity))  # Clamp to [0, 1]
    except (ValueError, TypeError):
        base_opacity = 0.5

    # Get color mode from query params (default to "single")
    color_mode = request.args.get("color_mode", "single")
    if color_mode not in ("single", "species"):
        color_mode = "single"

    # Get point size from query params (default to 6 pixels)
    try:
        point_size = int(request.args.get("point_size", 6))
        point_size = max(2, min(20, point_size))  # Clamp to [2, 20]
    except (ValueError, TypeError):
        point_size = 6

    # Generate species colors for "species" color mode
    species_colors = generate_species_colors(all_species)

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
        # Calculate opacity: base_opacity * count, capped at 1.0, then convert to 0-255
        point_opacity = min(1.0, base_opacity * count)
        alpha = int(point_opacity * 255)

        # Determine color based on color mode
        if color_mode == "species":
            if len(species_list) == 1:
                # Single species: use its assigned color
                r, g, b = species_colors.get(species_list[0], (255, 140, 0))
            else:
                # Multi-species: use neutral white
                r, g, b = 255, 255, 255
        else:
            # Single color mode: orange
            r, g, b = 255, 140, 0

        data.append({
            "latitude": lat,
            "longitude": lon,
            "count": count,
            "tooltip": format_tooltip(count, species_list, earliest, latest),
            "radius": point_size,
            "color": [r, g, b, alpha],
        })

    # Create pydeck visualization
    # Use radiusMinPixels and radiusMaxPixels to enforce fixed pixel size
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position=["longitude", "latitude"],
        get_fill_color="color",
        pickable=True,
        radius_min_pixels=point_size,
        radius_max_pixels=point_size,
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

    # Histogram query: observation counts in 7-day (weekly) buckets.
    # Uses the same species filter as the map.
    if filtering:
        hist_query = f"""
            SELECT
                toMonday(toDate(time)) AS week,
                COUNT(*) AS count
            FROM species_sightings
            WHERE species_name IN ({placeholders})
            GROUP BY week
            ORDER BY week
        """
        hist_result = client.query(hist_query, parameters=selected_species)
    else:
        hist_result = client.query("""
            SELECT
                toMonday(toDate(time)) AS week,
                COUNT(*) AS count
            FROM species_sightings
            GROUP BY week
            ORDER BY week
        """)

    max_count = max((row[1] for row in hist_result.result_rows), default=1)
    histogram_data = [
        {
            "week": row[0].strftime("%Y-%m-%d"),
            "label": row[0].strftime("%b %d"),
            "count": row[1],
            "height_pct": 100 * row[1] / max_count,
        }
        for row in hist_result.result_rows
    ]

    species_counts = load_species_counts()

    # Sort species by count in descending order
    all_species_sorted = sorted(
        all_species, key=lambda s: species_counts.get(s, 0), reverse=True
    )

    return render_template(
        "index.html",
        map_html=map_html,
        all_species=all_species_sorted,
        selected_species=selected_species,
        result_count=total_records,
        cell_count=len(data),
        species_counts=species_counts,
        histogram_data=histogram_data,
        opacity=base_opacity,
        color_mode=color_mode,
        point_size=point_size,
    )
