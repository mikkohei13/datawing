import json
import os
from pathlib import Path

import clickhouse_connect
import pydeck as pdk

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
SPECIES_COUNTS_CACHE = Path(__file__).parent / "species_counts_cache.json"


def get_client():
    return clickhouse_connect.get_client(host=CLICKHOUSE_HOST)


def load_species_counts():
    """Load species counts from cache file."""
    if SPECIES_COUNTS_CACHE.exists():
        with open(SPECIES_COUNTS_CACHE) as f:
            return json.load(f)
    return {}


def format_tooltip(count, earliest, latest):
    """Build a tooltip string for an aggregated grid cell."""
    date_str = f"{earliest.strftime('%Y-%m-%d')} — {latest.strftime('%Y-%m-%d')}"
    return f"{count} records\n{date_str}"


class ModuleContext:
    def __init__(self, module_name, flask_request, modules_registry):
        self.request = flask_request
        self._module_name = module_name
        self._modules = modules_registry

    @property
    def db(self):
        return get_client()

    def species_list(self):
        """Return (all_species_sorted, species_counts) tuple."""
        try:
            result = self.db.query(
                "SELECT DISTINCT species_name FROM species_sightings ORDER BY species_name"
            )
            all_species = [row[0] for row in result.result_rows]
        except Exception:
            all_species = sorted(load_species_counts().keys())

        species_counts = load_species_counts()
        all_species_sorted = sorted(
            all_species, key=lambda s: species_counts.get(s, 0), reverse=True
        )
        return all_species_sorted, species_counts

    def parse_map_controls(self):
        """Parse shared map controls from request: point_size, scale_with_map."""
        try:
            point_size = int(self.request.args.get("point_size", 6))
            point_size = max(2, min(20, point_size))
        except (ValueError, TypeError):
            point_size = 6
        scale_with_map = self.request.args.get("scale_with_map") == "on"
        return point_size, scale_with_map

    def render_map(self, data, scale_with_map=False, point_size=6):
        """Build pydeck map HTML from a list of point dicts.

        Each dict needs: latitude, longitude, color [r,g,b,a], tooltip (str).
        When scale_with_map=True, also needs radius (int).
        """
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

        html = deck.to_html(as_string=True)

        # Inject dark background to prevent white flash inside iframe
        dark_bg = "<style>html, body { background: #121212 !important; }</style>"
        html = html.replace("<head>", f"<head>{dark_bg}", 1)

        return html

    def render_template(self, template_name, **kwargs):
        from flask import render_template

        kwargs["modules"] = self._modules
        kwargs["current_module"] = self._module_name
        return render_template(
            f"modules/{self._module_name}/templates/{template_name}", **kwargs
        )
