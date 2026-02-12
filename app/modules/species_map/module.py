from core import format_tooltip

TITLE = "Species Map"
DESCRIPTION = "Fixed-color scatter plot of species observations"


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

    # Module-specific: opacity
    try:
        base_opacity = float(ctx.request.args.get("opacity", 0.5))
        base_opacity = max(0.0, min(1.0, base_opacity))
    except (ValueError, TypeError):
        base_opacity = 0.5

    total_records = 0
    data = []
    map_html = ""

    if selected_species:
        result = ctx.db.query(
            """
            SELECT
                latitude,
                longitude,
                COUNT(*) AS count,
                min(time) AS earliest,
                max(time) AS latest
            FROM species_sightings
            WHERE species_name = %s
            GROUP BY latitude, longitude
            """,
            parameters=[selected_species],
        )

        for row in result.result_rows:
            lat, lon, count, earliest, latest = row
            total_records += count
            alpha = int(min(1.0, base_opacity * count) * 255)
            radius_value = 500 if scale_with_map else point_size
            data.append(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "color": [38, 194, 255, alpha],
                    "tooltip": format_tooltip(count, earliest, latest),
                    "radius": radius_value,
                }
            )

        map_html = ctx.render_map(
            data, scale_with_map=scale_with_map, point_size=point_size
        )

    return ctx.render_template(
        "view.html",
        map_html=map_html,
        all_species=all_species,
        selected_species=selected_species,
        species_counts=species_counts,
        result_count=total_records,
        cell_count=len(data),
        opacity=base_opacity,
        point_size=point_size,
        scale_with_map=scale_with_map,
    )
