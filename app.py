"""Mini Maps - advanced shortest-route finder (Streamlit + OpenRouteService + Folium)."""

import json
import os

import folium
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from folium.plugins import Fullscreen, MiniMap
from streamlit_folium import st_folium

import algorithms as algo
import ors_client as ors

load_dotenv()
st.set_page_config(page_title="Mini Maps", page_icon="📍", layout="wide")

PREF_LABELS = {"shortest": "Shortest", "fastest": "Fastest", "recommended": "Recommended"}
ROUTE_COLORS = ["#16a34a", "#f97316", "#2563eb", "#9333ea", "#dc2626", "#0891b2", "#ca8a04"]
TILES = {"Standard": "OpenStreetMap", "Light": "CartoDB positron", "Dark": "CartoDB dark_matter"}


# ----------------------------------------------------------------------
# Sidebar settings
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")

    env_key = os.getenv("ORS_API_KEY", "")
    if env_key:
        api_key = env_key
        st.caption("🔑 API key loaded from .env")
    else:
        api_key = st.text_input(
            "OpenRouteService API key",
            type="password",
            help="Free key from account.heigit.org. Or put ORS_API_KEY in a .env file.",
        )

    profile_name = st.selectbox("Travel mode", list(ors.PROFILES))
    profile = ors.PROFILES[profile_name]

    prefs = st.multiselect(
        "Route types to compare",
        list(PREF_LABELS),
        default=list(PREF_LABELS),
        format_func=PREF_LABELS.get,
        help="'Shortest' minimises distance, 'Fastest' minimises time.",
    )
    want_alts = st.checkbox(
        "Also fetch alternative routes",
        value=True,
        help="Works only without via-stops, and the free API limits it to shorter trips (about 100 km).",
    )
    india_only = st.checkbox("Search places in India only", value=True)
    tile_name = st.selectbox("Map style", list(TILES))
    show_turns = st.checkbox("Show turn markers on the map", value=False)

    mileage, fuel_price = 15.0, 100.0
    if profile == "driving-car":
        st.subheader("⛽ Fuel cost")
        mileage = st.number_input("Mileage (km/l)", min_value=1.0, value=15.0, step=1.0)
        fuel_price = st.number_input("Fuel price (₹/l)", min_value=1.0, value=100.0, step=1.0)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def fmt_duration(seconds):
    hours, minutes = divmod(round(seconds / 60), 60)
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def latlngs(feature):
    return [[c[1], c[0]] for c in feature["geometry"]["coordinates"]]


@st.cache_data(show_spinner=False, ttl=3600)
def cached_geocode(key, text, india):
    return ors.geocode(key, text, country="IND" if india else None)


def place_picker(label, key, placeholder):
    """Text box + list of matching places. Returns {'label', 'coords'} or None."""
    text = st.text_input(label, key=f"{key}_text", placeholder=placeholder)
    if not text.strip():
        return None
    if not api_key:
        st.warning("Add your API key first.")
        return None
    try:
        matches = cached_geocode(api_key, text.strip(), india_only)
    except ors.ORSError as error:
        st.error(str(error))
        return None
    if not matches:
        st.warning(f"No place found for '{text}'.")
        return None
    if len(matches) == 1:
        st.caption(f"📍 {matches[0]['label']}")
        return matches[0]
    index = st.selectbox(
        "Did you mean",
        range(len(matches)),
        format_func=lambda i: matches[i]["label"],
        key=f"{key}_pick",
    )
    return matches[index]


def fetch_routes(coords):
    """Collect shortest / fastest / recommended (and alternative) routes, de-duplicated."""
    records, by_signature, notes = [], {}, []

    def add(feature, tag):
        summary = feature["properties"]["summary"]
        signature = (round(summary["distance"], 2), round(summary["duration"]))
        if signature in by_signature:
            by_signature[signature]["tags"].append(tag)
            return
        record = {
            "tags": [tag],
            "feature": feature,
            "distance": summary["distance"],
            "duration": summary["duration"],
        }
        by_signature[signature] = record
        records.append(record)

    for pref in prefs or ["recommended"]:
        add(ors.directions(api_key, coords, profile, pref)[0], PREF_LABELS[pref])

    if want_alts and len(coords) == 2:
        try:
            for feature in ors.directions(api_key, coords, profile, "recommended", True):
                add(feature, f"Alternative {len(records)}")
        except ors.ORSError as error:
            notes.append(f"Alternative routes unavailable for this trip: {error}")
    elif want_alts:
        notes.append("Alternative routes are skipped when via-stops are used.")

    for record in records:
        record["label"] = " / ".join(record["tags"])
    return records, notes


def display_map(result, selected):
    records = result["records"]
    all_points = [p for r in records for p in latlngs(r["feature"])]

    route_map = folium.Map(tiles=TILES[tile_name], control_scale=True)
    Fullscreen().add_to(route_map)
    MiniMap(toggle_display=True).add_to(route_map)

    order = [i for i in range(len(records)) if i != selected] + [selected]
    for i in order:
        record = records[i]
        is_selected = i == selected
        folium.PolyLine(
            latlngs(record["feature"]),
            color=ROUTE_COLORS[i % len(ROUTE_COLORS)],
            weight=8 if is_selected else 4,
            opacity=0.95 if is_selected else 0.5,
            tooltip=f"{record['label']}: {record['distance']:.1f} km, {fmt_duration(record['duration'])}",
        ).add_to(route_map)

    last = len(result["coords"]) - 1
    for i, (name, coord) in enumerate(zip(result["names"], result["coords"])):
        color = "green" if i == 0 else "red" if i == last else "orange"
        folium.Marker(
            [coord[1], coord[0]], tooltip=name, popup=name, icon=folium.Icon(color=color)
        ).add_to(route_map)

    if show_turns:
        feature = records[selected]["feature"]
        coords = feature["geometry"]["coordinates"]
        for segment in feature["properties"].get("segments", []):
            for step in segment.get("steps", []):
                point = coords[step["way_points"][0]]
                folium.CircleMarker(
                    [point[1], point[0]],
                    radius=4,
                    color="#111827",
                    fill=True,
                    fill_opacity=0.9,
                    tooltip=step["instruction"],
                ).add_to(route_map)

    lats = [p[0] for p in all_points]
    lons = [p[1] for p in all_points]
    route_map.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    st_folium(route_map, use_container_width=True, height=520, returned_objects=[], key="route_map")


def show_results(result):
    records = result["records"]
    shortest = min(records, key=lambda r: r["distance"])
    fastest = min(records, key=lambda r: r["duration"])

    for note in result["notes"]:
        st.info(note)

    columns = st.columns(4)
    columns[0].metric("Shortest distance", f"{shortest['distance']:.1f} km")
    columns[1].metric("Fastest time", fmt_duration(fastest["duration"]))
    columns[2].metric("Routes found", len(records))
    if result["profile"] == "driving-car":
        cost = shortest["distance"] / result["mileage"] * result["fuel_price"]
        columns[3].metric("Fuel cost (shortest)", f"₹{cost:,.0f}")

    st.subheader("🗺️ Route map")
    selected = st.radio(
        "Highlight route",
        range(len(records)),
        index=records.index(shortest),
        format_func=lambda i: (
            f"{records[i]['label']} - {records[i]['distance']:.1f} km, "
            f"{fmt_duration(records[i]['duration'])}"
        ),
        horizontal=True,
    )
    display_map(result, selected)

    st.subheader("📊 Route comparison")
    table = pd.DataFrame(
        {
            "Route": [r["label"] for r in records],
            "Distance (km)": [round(r["distance"], 2) for r in records],
            "Time (min)": [round(r["duration"] / 60) for r in records],
            "Avg speed (km/h)": [round(r["distance"] / (r["duration"] / 3600), 1) for r in records],
        }
    )
    left, right = st.columns([3, 2])
    left.dataframe(table, hide_index=True, width="stretch")
    right.bar_chart(table.set_index("Route")[["Distance (km)"]])

    chosen = records[selected]
    st.subheader(f"🧭 Turn-by-turn: {chosen['label']}")
    steps = [s for seg in chosen["feature"]["properties"].get("segments", []) for s in seg["steps"]]
    if steps:
        st.dataframe(
            pd.DataFrame(
                {
                    "#": range(1, len(steps) + 1),
                    "Instruction": [s["instruction"] for s in steps],
                    "Distance (km)": [round(s["distance"], 2) for s in steps],
                    "Time (min)": [round(s["duration"] / 60, 1) for s in steps],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    st.subheader("📤 Export")
    name = " to ".join([result["names"][0].split(",")[0], result["names"][-1].split(",")[0]])
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button(
        "GeoJSON", json.dumps(chosen["feature"]), "route.geojson", "application/geo+json"
    )
    d2.download_button("GPX", ors.to_gpx(chosen["feature"], name), "route.gpx", "application/gpx+xml")
    d3.download_button("Comparison CSV", table.to_csv(index=False), "routes.csv", "text/csv")
    d4.link_button("Open in Google Maps", ors.google_maps_url(result["coords"], result["profile"]))
    st.caption("Google Maps may pick its own path between your start, stops and destination.")


# ----------------------------------------------------------------------
# Tab 1: Route finder
# ----------------------------------------------------------------------
def route_tab():
    st.write("Find the shortest, fastest and alternative routes between places in India.")
    if not api_key:
        st.info("Add your free OpenRouteService API key (sidebar or .env file) to start.")

    n_via = st.slider("Via-stops (optional)", 0, 3, 0)
    left, right = st.columns(2)
    with left:
        source = place_picker("Starting location", "src", "Gachibowli, Hyderabad")
    with right:
        destination = place_picker("Destination", "dst", "Charminar, Hyderabad")
    via_places = []
    for i in range(n_via):
        via_places.append(place_picker(f"Via-stop {i + 1}", f"via{i}", "e.g. Kurnool"))

    if "result" not in st.session_state:
        st.session_state.result = None

    if st.button("Find routes", type="primary", disabled=not api_key):
        points = [source] + via_places + [destination]
        if any(p is None for p in points):
            st.warning("Enter and pick every location first.")
        elif any(a["coords"] == b["coords"] for a, b in zip(points, points[1:])):
            st.warning("Two consecutive locations are the same place.")
        else:
            try:
                with st.spinner("Finding routes..."):
                    coords = [p["coords"] for p in points]
                    records, notes = fetch_routes(coords)
                st.session_state.result = {
                    "names": [p["label"] for p in points],
                    "coords": coords,
                    "records": records,
                    "notes": notes,
                    "profile": profile,
                    "mileage": mileage,
                    "fuel_price": fuel_price,
                }
            except ors.ORSError as error:
                st.session_state.result = None
                st.error(str(error))

    if st.session_state.result:
        show_results(st.session_state.result)


# ----------------------------------------------------------------------
# Tab 2: Algorithm lab (works offline, no API key needed)
# ----------------------------------------------------------------------
def lab_tab():
    st.write(
        "See how classic AI search algorithms solve the shortest-path problem on a "
        "graph of South Indian cities. A* reaches the goal by exploring fewer cities."
    )
    graph = algo.build_graph()
    cities = sorted(algo.CITIES)
    left, right = st.columns(2)
    start = left.selectbox("Start city", cities, index=cities.index("Kurnool"))
    goal = right.selectbox("Goal city", cities, index=cities.index("Chennai"))
    if start == goal:
        st.warning("Pick two different cities.")
        return

    results = algo.run_all(graph, start, goal)
    table = pd.DataFrame(
        {
            "Algorithm": list(results),
            "Distance (km)": [r["distance"] for r in results.values()],
            "Cities explored": [len(r["explored"]) for r in results.values()],
            "Route": [" → ".join(r["path"]) for r in results.values()],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    saved = len(results["Dijkstra"]["explored"]) - len(results["A*"]["explored"])
    st.success(
        f"A* explored {len(results['A*']['explored'])} cities vs "
        f"{len(results['Dijkstra']['explored'])} for Dijkstra ({saved} fewer) "
        "and found the same shortest distance."
    )

    pick = st.radio("Show on map", list(results), index=2, horizontal=True)
    result = results[pick]
    lab_map = folium.Map(location=[15.5, 79.0], zoom_start=6, tiles=TILES[tile_name])
    for a, b in algo.ROADS:
        folium.PolyLine([algo.CITIES[a], algo.CITIES[b]], color="#9ca3af", weight=2).add_to(lab_map)
    folium.PolyLine(
        [algo.CITIES[c] for c in result["path"]], color="#dc2626", weight=6,
        tooltip=f"{pick}: {result['distance']} km",
    ).add_to(lab_map)
    for order, city in enumerate(result["explored"], start=1):
        on_path = city in result["path"]
        folium.CircleMarker(
            algo.CITIES[city],
            radius=9 if on_path else 6,
            color="#dc2626" if on_path else "#2563eb",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"#{order} explored: {city}",
        ).add_to(lab_map)
    st_folium(lab_map, use_container_width=True, height=480, returned_objects=[], key="lab_map")
    st.caption("Hover a dot to see the order in which the algorithm explored each city.")


# ----------------------------------------------------------------------
# Tab 3: About
# ----------------------------------------------------------------------
def about_tab():
    st.markdown(
        """
**How it works**
1. Place names are converted to coordinates (geocoding).
2. The routing API returns the *shortest*, *fastest* and *recommended* routes (plus alternatives when possible).
3. The app compares them, highlights the best, and draws everything on an interactive map.
4. The **Algorithm Lab** shows the AI search side: BFS, Dijkstra and A*.

**Tech stack:** Python, Streamlit, OpenRouteService (HeiGIT), Folium, OpenStreetMap, Pandas.
        """
    )


tab_route, tab_lab, tab_about = st.tabs(["📍 Route Finder", "🧠 Algorithm Lab (AI)", "ℹ️ About"])
st.title("📍 Mini Maps")
with tab_route:
    route_tab()
with tab_lab:
    lab_tab()
with tab_about:
    about_tab()
