import colorsys
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


def day_of_year_to_rgb(day):
    """Convert day-of-year (1-366) to an RGB tuple using a rainbow scale.

    Days 1-181 (Jan 1 – Jun 30) span red to violet.
    Days above 181 return white.
    """
    if day > 181:
        return [255, 255, 255]
    hue = (day - 1) / 180 * 0.83  # 0.0 to ~0.83 (red to violet)
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return [int(r * 255), int(g * 255), int(b * 255)]


def format_tooltip(count, earliest, latest):
    """Build a tooltip string for an aggregated grid cell."""
    date_str = f"{earliest.strftime('%Y-%m-%d')} — {latest.strftime('%Y-%m-%d')}"
    return f"{count} records\n{date_str}"


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

    # Get selected species from query params (single value, None if not set)
    selected_species = request.args.get("species")

    # Get opacity setting from query params (default to 0.5)
    try:
        base_opacity = float(request.args.get("opacity", 0.5))
        base_opacity = max(0.0, min(1.0, base_opacity))  # Clamp to [0, 1]
    except (ValueError, TypeError):
        base_opacity = 0.5

    # Get point size from query params (default to 6 pixels)
    try:
        point_size = int(request.args.get("point_size", 6))
        point_size = max(2, min(20, point_size))  # Clamp to [2, 20]
    except (ValueError, TypeError):
        point_size = 6

    # Whether dots should scale with the map zoom level
    scale_with_map = request.args.get("scale_with_map") == "on"

    # Color mode: "fixed" (orange) or "day_of_year" (rainbow)
    color_by = request.args.get("color_by", "fixed")

    # Only query data if a species is selected
    total_records = 0
    data = []
    histogram_data = []

    if selected_species:
        # Aggregation query: one row per grid cell with count and date range.
        result = client.query("""
            SELECT
                latitude,
                longitude,
                COUNT(*) AS count,
                min(time) AS earliest,
                max(time) AS latest,
                min(dayOfYear(time)) AS min_day
            FROM species_sightings
            WHERE species_name = %s
            GROUP BY latitude, longitude
        """, parameters=[selected_species])

        # Build pydeck data from aggregated rows
        for row in result.result_rows:
            lat, lon, count, earliest, latest, min_day = row
            total_records += count
            point_opacity = min(1.0, base_opacity * count)
            alpha = int(point_opacity * 255)

            # In scale-with-map mode, radius is fixed
            radius_value = 500 if scale_with_map else point_size

            if color_by == "day_of_year":
                rgb = day_of_year_to_rgb(min_day)
                color = rgb + [alpha]
            else:
                color = [255, 140, 0, alpha]

            data.append({
                "latitude": lat,
                "longitude": lon,
                "count": count,
                "tooltip": format_tooltip(count, earliest, latest),
                "radius": radius_value,
                "color": color,
            })

        # Histogram query: observation counts in weekly buckets.
        hist_result = client.query("""
            SELECT
                toMonday(toDate(time)) AS week,
                COUNT(*) AS count
            FROM species_sightings
            WHERE species_name = %s
            GROUP BY week
            ORDER BY week
        """, parameters=[selected_species])

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

    # Create pydeck visualization
    if scale_with_map:
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=data,
            get_position=["longitude", "latitude"],
            get_fill_color="color",
            get_radius="radius",
            pickable=True,
            radius_min_pixels=1,
        )
    else:
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
        point_size=point_size,
        scale_with_map=scale_with_map,
        color_by=color_by,
    )
