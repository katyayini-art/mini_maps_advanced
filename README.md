# Mini Maps - Advanced Shortest Route Finder

A Python web app that finds the shortest, fastest and alternative routes between
places in India, shows them on an interactive map, and demonstrates the AI search
algorithms (BFS, Dijkstra, A*) behind shortest-path finding.

## Features
**Route Finder**
- Place search with a "Did you mean" list of matches (not just the first result)
- Up to 3 via-stops (multi-stop trips)
- Compares the truly shortest, fastest and recommended routes, plus alternatives
- Travel modes: car, heavy vehicle, bike, walking
- Distance, time, average speed and fuel-cost estimate
- Turn-by-turn directions and optional turn markers on the map
- Map styles (standard, light, dark), fullscreen and minimap
- Export: GeoJSON, GPX, comparison CSV, and "Open in Google Maps" link
- Friendly errors for a bad API key, rate limits and network problems
- Cached place searches to save API quota

**Algorithm Lab (AI)** - works offline, no API key needed
- BFS vs Dijkstra vs A* on a graph of 14 South Indian cities
- Compares distance and number of cities explored
- Map shows the path and the order in which cities were explored

## Project structure
```
app.py            Streamlit user interface
ors_client.py     API calls (geocoding, directions), GPX and Google Maps link
algorithms.py     BFS, Dijkstra, A* implementations
requirements.txt  Dependencies
.env.example      Template for your API key
```

## How to run
1. Install Python 3.9 or newer.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Get a free API key from https://account.heigit.org and create a `.env` file:
   ```
   ORS_API_KEY=your_api_key
   ```
   (You can also paste the key in the app's sidebar instead.)
4. Start the app:
   ```
   streamlit run app.py
   ```
   The Algorithm Lab tab works even without a key.

## Algorithms
| Algorithm | Type | Shortest distance? | Idea |
|-----------|------|--------------------|------|
| BFS | Uninformed | No (fewest stops) | Explore level by level |
| Dijkstra | Uninformed | Yes | Expand the cheapest-so-far city |
| A* | Informed | Yes | f(n) = g(n) + h(n), h = straight-line distance |

The A* heuristic is admissible because road distance is modelled as 1.3 x
straight-line distance, so it never overestimates.

## Viva questions
1. Why does BFS fail on weighted graphs? It ignores edge weights.
2. Why is A* faster than Dijkstra? The heuristic steers the search toward the goal.
3. What is an admissible heuristic? One that never overestimates the true cost.
4. Why request "shortest" and "fastest" separately? Shortest distance and least time are different goals and often pick different roads.
5. What is geocoding? Converting a place name into latitude and longitude.

## Limits
- Free API: about 2000 requests/day and 40/minute; alternative routes work only for shorter trips.
- Google Maps link opens your trip in Google Maps but Google may choose its own path.

## Ideas to extend
- Real road graph with OSMnx and custom A* on it
- Traffic-aware times, tolls, or isochrone maps (areas reachable in N minutes)
- Deploy free on Streamlit Community Cloud (add ORS_API_KEY under Secrets)
