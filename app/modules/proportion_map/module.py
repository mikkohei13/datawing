import colorsys
import json
from pathlib import Path

TITLE = "Proportion Map"
DESCRIPTION = "Rainbow-colored map showing species proportion relative to expected"

# Cap for the observed/expected ratio — locations at or above this are full red
RATIO_CAP = 5.0

# Floor for expected proportion to avoid extreme ratios for very rare species
EXPECTED_FLOOR = 0.005

_proportions_file = Path(__file__).parent.parent.parent / "species_proportions.json"
_species_proportions = {}
if _proportions_file.exists():
    with open(_proportions_file) as f:
        _species_proportions = json.load(f)


def ratio_to_rainbow(ratio):
    """Convert a ratio (0.0–RATIO_CAP) to an RGB list using a rainbow scale.

    0.0 (low) = blue, mid = green, RATIO_CAP (high) = red.
    Uses HSV hue going from 240° (blue) down to 0° (red).
    """
    t = min(ratio / RATIO_CAP, 1.0)
    hue = (1.0 - t) * 0.667  # 0.667 (blue) → 0.0 (red)
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
    map_html = ""
    expected = 0.0

    if selected_species:
        expected = max(
            _species_proportions.get(selected_species, EXPECTED_FLOOR),
            EXPECTED_FLOOR,
        )

        # Single query: get total and species-specific counts per location
        result = ctx.db.query(
            """
            SELECT
                latitude,
                longitude,
                COUNT(*) AS total_count,
                countIf(species_name = %s) AS species_count
            FROM species_sightings
            GROUP BY latitude, longitude
            HAVING species_count > 0
            """,
            parameters=[selected_species],
        )

        for row in result.result_rows:
            lat, lon, total_count, species_count = row
            total_records += species_count
            proportion = species_count / total_count
            ratio = proportion / expected
            rgb = ratio_to_rainbow(ratio)
            radius_value = 500 if scale_with_map else point_size
            data.append(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "color": rgb + [200],
                    "tooltip": (
                        f"{species_count}/{total_count} records"
                        f" ({proportion:.1%})"
                        f"\n{ratio:.1f}× expected"
                    ),
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
        expected_proportion=expected,
        ratio_cap=RATIO_CAP,
        point_size=point_size,
        scale_with_map=scale_with_map,
    )
