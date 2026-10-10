"""Unit tests for the blocked-route checker's pure graph logic
(app/impact/routes.py) -- a small synthetic networkx graph, no network
calls, no real OSM fetch."""

import networkx as nx

from app.impact.routes import _evaluate, _nearest_hospital


def _line_graph(n: int) -> nx.MultiDiGraph:
    """0 -- 1 -- 2 -- ... -- n, each edge length 100m, both directions."""
    g = nx.MultiDiGraph()
    for i in range(n):
        g.add_node(i, x=float(i), y=0.0)
    for i in range(n - 1):
        g.add_edge(i, i + 1, key=0, length=100.0)
        g.add_edge(i + 1, i, key=0, length=100.0)
    return g


def test_evaluate_none_when_blocked_edge_not_on_shortest_path():
    # A detour branch (node 10) that isn't on the 0->4 shortest path at all.
    g = _line_graph(5)
    g.add_node(10, x=0.5, y=1.0)
    g.add_edge(0, 10, key=0, length=50.0)
    g.add_edge(10, 0, key=0, length=50.0)

    result = _evaluate(g, 0, 4, [(0, 10, 0)])
    assert result["route_impact"] == "none"
    assert result["detour_m"] == 0.0


def test_evaluate_detour_when_alternate_path_is_longer():
    g = _line_graph(3)  # 0-1-2, blocking 0-1 with no alternate -> no_alternative
    # add a longer alternate path 0 -> 3 -> 1
    g.add_node(3, x=0.5, y=1.0)
    g.add_edge(0, 3, key=0, length=200.0)
    g.add_edge(3, 1, key=0, length=200.0)
    g.add_edge(1, 3, key=0, length=200.0)
    g.add_edge(3, 0, key=0, length=200.0)

    result = _evaluate(g, 0, 2, [(0, 1, 0), (1, 0, 0)])
    assert result["route_impact"] == "detour"
    assert result["detour_m"] > 0

    # graph must be restored after _evaluate (edges added back)
    assert g.has_edge(0, 1, 0)


def test_evaluate_no_alternative_when_graph_disconnected():
    g = _line_graph(3)  # 0-1-2, no other path
    result = _evaluate(g, 0, 2, [(0, 1, 0), (1, 0, 0)])
    assert result["route_impact"] == "no_alternative"
    assert result["detour_m"] is None
    assert g.has_edge(0, 1, 0)  # restored


def test_evaluate_unknown_when_unreachable_before_removal():
    g = nx.MultiDiGraph()
    g.add_node(0, x=0.0, y=0.0)
    g.add_node(1, x=1.0, y=0.0)  # disconnected from 0
    result = _evaluate(g, 0, 1, [])
    assert result["route_impact"] == "unknown"
    assert result["detour_m"] is None


def test_nearest_hospital_picks_closest():
    hospitals = [
        {"lat": 11.0, "lon": 76.0, "name": "Far"},
        {"lat": 11.001, "lon": 76.001, "name": "Near"},
    ]
    h = _nearest_hospital(11.0, 76.0, hospitals)
    assert h["name"] == "Far"


def test_nearest_hospital_empty_list_returns_none():
    assert _nearest_hospital(11.0, 76.0, []) is None
