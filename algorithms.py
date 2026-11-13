"""AI search algorithms (BFS, Dijkstra, A*) on a small map of South Indian cities."""

import heapq
import math
from collections import deque

CITIES = {
    "Kurnool": (15.83, 78.04),
    "Hyderabad": (17.38, 78.48),
    "Mahbubnagar": (16.74, 77.99),
    "Anantapur": (14.68, 77.60),
    "Kadapa": (14.47, 78.82),
    "Tirupati": (13.63, 79.42),
    "Chennai": (13.08, 80.27),
    "Bengaluru": (12.97, 77.59),
    "Nellore": (14.44, 79.99),
    "Ongole": (15.50, 80.05),
    "Guntur": (16.31, 80.44),
    "Vijayawada": (16.51, 80.65),
    "Visakhapatnam": (17.69, 83.22),
    "Nandyal": (15.48, 78.48),
}

ROADS = [
    ("Kurnool", "Mahbubnagar"), ("Mahbubnagar", "Hyderabad"),
    ("Kurnool", "Nandyal"), ("Nandyal", "Kadapa"),
    ("Kurnool", "Anantapur"), ("Anantapur", "Bengaluru"),
    ("Anantapur", "Kadapa"), ("Kadapa", "Tirupati"),
    ("Tirupati", "Chennai"), ("Tirupati", "Bengaluru"),
    ("Kadapa", "Nellore"), ("Nellore", "Chennai"),
    ("Nellore", "Ongole"), ("Ongole", "Guntur"),
    ("Guntur", "Vijayawada"), ("Vijayawada", "Visakhapatnam"),
    ("Hyderabad", "Vijayawada"), ("Nandyal", "Guntur"),
    ("Bengaluru", "Chennai"),
]


def haversine(a, b):
    """Straight-line distance in km between two cities."""
    (lat1, lon1), (lat2, lon2) = CITIES[a], CITIES[b]
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def build_graph():
    """Adjacency list city -> [(neighbour, km)].
    Road length = 1.3 x straight line, so the A* heuristic never overestimates."""
    graph = {c: [] for c in CITIES}
    for a, b in ROADS:
        d = round(haversine(a, b) * 1.3, 1)
        graph[a].append((b, d))
        graph[b].append((a, d))
    return graph


def _rebuild(parent, goal):
    path = []
    while goal is not None:
        path.append(goal)
        goal = parent[goal]
    return path[::-1]


def _cost(graph, path):
    weight = {(a, b): d for a in graph for b, d in graph[a]}
    return round(sum(weight[(path[i], path[i + 1])] for i in range(len(path) - 1)), 1)


def bfs(graph, start, goal):
    parent, queue, explored = {start: None}, deque([start]), []
    while queue:
        node = queue.popleft()
        explored.append(node)
        if node == goal:
            path = _rebuild(parent, goal)
            return path, _cost(graph, path), explored
        for nxt, _ in graph[node]:
            if nxt not in parent:
                parent[nxt] = node
                queue.append(nxt)
    return None, math.inf, explored


def dijkstra(graph, start, goal):
    dist, parent = {start: 0}, {start: None}
    heap, explored, done = [(0, start)], [], set()
    while heap:
        d, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        explored.append(node)
        if node == goal:
            return _rebuild(parent, goal), round(d, 1), explored
        for nxt, w in graph[node]:
            if d + w < dist.get(nxt, math.inf):
                dist[nxt], parent[nxt] = d + w, node
                heapq.heappush(heap, (d + w, nxt))
    return None, math.inf, explored


def a_star(graph, start, goal):
    g, parent = {start: 0}, {start: None}
    heap, explored, done = [(haversine(start, goal), start)], [], set()
    while heap:
        _, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        explored.append(node)
        if node == goal:
            return _rebuild(parent, goal), round(g[node], 1), explored
        for nxt, w in graph[node]:
            ng = g[node] + w
            if ng < g.get(nxt, math.inf):
                g[nxt], parent[nxt] = ng, node
                heapq.heappush(heap, (ng + haversine(nxt, goal), nxt))
    return None, math.inf, explored


def run_all(graph, start, goal):
    """Run all three algorithms; returns {name: {'path', 'distance', 'explored'}}."""
    results = {}
    for name, fn in (("BFS", bfs), ("Dijkstra", dijkstra), ("A*", a_star)):
        path, dist, explored = fn(graph, start, goal)
        results[name] = {"path": path, "distance": dist, "explored": explored}
    return results
