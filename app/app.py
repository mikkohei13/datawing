import os

import clickhouse_connect
import pydeck as pdk
from flask import Flask

app = Flask(__name__)

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
        <h1>No data yet</h1>
        <p>Run the seed script to populate data:</p>
        <pre>docker compose exec app python scripts/seed_data.py</pre>
        """

    # Create pydeck visualization
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position=["longitude", "latitude"],
        get_radius=50000,
        get_fill_color=[255, 140, 0, 200],
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=0,
        longitude=0,
        zoom=1,
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{species_name}"},
    )

    return deck.to_html(as_string=True)
