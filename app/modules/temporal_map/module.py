import colorsys

from core import format_tooltip

TITLE = "Temporal Map"
DESCRIPTION = "Day-of-year colored map with weekly histogram"


def day_of_year_to_rgb(day):
    """Convert day-of-year (1-366) to an RGB tuple using a rainbow scale.

    Days 1-181 (Jan 1 - Jun 30) span red to violet.
    Days above 181 return white.
    """
    if day > 181:
        return [255, 255, 255]
    hue = (day - 1) / 180 * 0.83  # 0.0 to ~0.83 (red to violet)
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return [int(r * 255), int(g * 255), int(b * 255)]


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

    total_records = 0
    data = []
    histogram_data = []
    map_html = ""

    if selected_species:
        result = ctx.db.query(
            """
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
            """,
            parameters=[selected_species],
        )

        for row in result.result_rows:
            lat, lon, count, earliest, latest, min_day = row
            total_records += count
            rgb = day_of_year_to_rgb(min_day)
            radius_value = 500 if scale_with_map else point_size
            data.append(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "color": rgb + [200],
                    "tooltip": format_tooltip(count, earliest, latest),
                    "radius": radius_value,
                }
            )

        # Histogram query: observation counts in weekly buckets.
        hist_result = ctx.db.query(
            """
            SELECT
                toMonday(toDate(time)) AS week,
                COUNT(*) AS count
            FROM species_sightings
            WHERE species_name = %s
            GROUP BY week
            ORDER BY week
            """,
            parameters=[selected_species],
        )

        max_count = max((row[1] for row in hist_result.result_rows), default=1)
        for row in hist_result.result_rows:
            week_date = row[0]
            doy = week_date.timetuple().tm_yday
            r, g, b = day_of_year_to_rgb(doy)
            histogram_data.append(
                {
                    "week": week_date.strftime("%Y-%m-%d"),
                    "label": week_date.strftime("%b %d"),
                    "count": row[1],
                    "height_pct": 100 * row[1] / max_count,
                    "color": f"rgb({r}, {g}, {b})",
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
        histogram_data=histogram_data,
        point_size=point_size,
        scale_with_map=scale_with_map,
    )
