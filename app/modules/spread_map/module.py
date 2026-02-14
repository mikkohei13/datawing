import json

from flask import render_template as flask_render_template

TITLE = "Spread Map"
DESCRIPTION = "Animated map showing how a species spreads through the year"


def render(ctx):
    all_species, species_counts = ctx.species_list()

    if not all_species:
        return (
            "<h1>No data yet!</h1>"
            "<p>Run the seed script to populate data:</p>"
            "<pre>docker compose exec app python scripts/seed_data.py</pre>"
        )

    selected_species = ctx.request.args.get("species")
    point_size, scale_with_map = ctx.parse_map_controls()

    # Module-specific: fade duration and animation speed
    try:
        fade_days = int(ctx.request.args.get("fade_days", 14))
        fade_days = max(1, min(60, fade_days))
    except (ValueError, TypeError):
        fade_days = 14

    try:
        speed = int(ctx.request.args.get("speed", 20))
        speed = max(5, min(100, speed))
    except (ValueError, TypeError):
        speed = 20

    total_records = 0
    point_count = 0
    map_html = ""

    if selected_species:
        # Each row is a unique (location, day) group — no coordinate rounding
        # needed since lat/lon are already stored at 2-decimal precision.
        result = ctx.db.query(
            """
            SELECT
                latitude,
                longitude,
                day_of_year,
                COUNT(*) AS count
            FROM species_sightings
            WHERE species_name = %s
            GROUP BY latitude, longitude, day_of_year
            ORDER BY day_of_year
            """,
            parameters=[selected_species],
        )

        points = []
        for row in result.result_rows:
            lat, lon, day, count = row
            total_records += count
            points.append([lat, lon, day])
        point_count = len(points)

        # Build standalone deck.gl HTML (bypasses pydeck for animation support)
        map_html = flask_render_template(
            "modules/spread_map/templates/map.html",
            points_json=json.dumps(points),
            point_size=point_size,
            scale_with_map=scale_with_map,
            fade_days=fade_days,
            speed=speed,
        )

    return ctx.render_template(
        "view.html",
        map_html=map_html,
        all_species=all_species,
        selected_species=selected_species,
        species_counts=species_counts,
        result_count=total_records,
        cell_count=point_count,
        point_size=point_size,
        scale_with_map=scale_with_map,
        fade_days=fade_days,
        speed=speed,
    )
