import colorsys
from datetime import datetime

TITLE = "Temporal Quantile Map"
DESCRIPTION = "Day-of-year quantile colored map with weekly histogram"

DEFAULT_QUANTILE = 0.05


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


def parse_quantile(raw_quantile):
    """Parse quantile from request args and clamp to 0..1.

    Accepts either decimal form (0.05) or percent form (5 => 0.05).
    """
    try:
        quantile = float(raw_quantile)
    except (TypeError, ValueError):
        return DEFAULT_QUANTILE

    if quantile > 1:
        quantile = quantile / 100.0
    return max(0.0, min(1.0, quantile))


def format_quantile_tooltip(count, earliest, quantile_day):
    """Build a tooltip string for a quantile-colored grid cell."""
    earliest_str = earliest.strftime("%Y-%m-%d")
    quantile_mm_dd = datetime.strptime(f"2000-{int(quantile_day):03d}", "%Y-%j").strftime(
        "%m-%d"
    )
    return (
        f"{count} records\n"
        f"Earliest: {earliest_str}\n"
        f"Quantile day: {quantile_mm_dd}"
    )


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
    quantile = parse_quantile(ctx.request.args.get("quantile"))
    quantile_literal = f"{quantile:.6f}".rstrip("0").rstrip(".")

    total_records = 0
    data = []
    histogram_data = []
    map_html = ""

    if selected_species:
        result = ctx.db.query(
            f"""
            SELECT
                latitude,
                longitude,
                COUNT(*) AS count,
                min(time) AS earliest,
                quantileExact({quantile_literal})(day_of_year) AS quantile_day
            FROM species_sightings
            WHERE species_name = %s
            GROUP BY latitude, longitude
            """,
            parameters=[selected_species],
        )

        for row in result.result_rows:
            lat, lon, count, earliest, quantile_day = row
            total_records += count
            doy = max(1, min(366, int(quantile_day)))
            rgb = day_of_year_to_rgb(doy)
            radius_value = 500 if scale_with_map else point_size
            data.append(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "color": rgb + [200],
                    "tooltip": format_quantile_tooltip(count, earliest, doy),
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
        quantile=quantile,
        quantile_percent=round(quantile * 100, 1),
    )
