"""Blocked-route checker: for kept polygons that intersect an OSM road,
check whether the nearest hospital is still reachable on the OSM drive
road graph (osmnx) with that road's edges removed.

route_impact values:
  none           -- polygon doesn't touch a road, or the road it touches
                     isn't on anyone's shortest path to the hospital anyway
  detour         -- hospital still reachable, but the shortest path is
                     longer with the blocked edges removed (see detour_m)
  no_alternative -- no path to the hospital exists once those edges are
                     removed
  unknown        -- couldn't compute (no road graph, no hospital data,
                     nodes not found) -- never silently reported as "none"

The graph is a drive-network osmnx MultiDiGraph, cached to disk as
GraphML keyed by the (buffered) analysis bbox -- same pattern and buffer
as app/impact/facilities.py's Overpass cache, since a hospital trip would
realistically use the same catchment.

Always labeled "possible blockage — verify on ground" in the UI
(app.config.ROUTE_BLOCKAGE_WORDING) -- this is a graph-reachability
signal, not a confirmed on-the-ground closure.
"""

from pathlib import Path
from typing import Optional

import networkx as nx
import osmnx as ox

from app import config
from app.db import DATA_DIR

# osmnx's own HTTP response cache -- defaults to ./cache (cwd-relative, not
# gitignored); point it at data/ like everything else this project caches.
ox.settings.cache_folder = str(DATA_DIR / "osmnx_http_cache")


class RouteGraphError(RuntimeError):
    """Raised when the OSM drive-network graph can't be fetched."""


def _cache_path(buffered_bounds: tuple, cache_dir: Path) -> Path:
    key = "_".join(f"{v:.3f}" for v in buffered_bounds)
    return cache_dir / f"roadgraph_{key}.graphml"


def get_road_graph(bounds_4326: tuple, cache_dir: Path) -> nx.MultiDiGraph:
    west, south, east, north = bounds_4326
    buf = config.ROUTE_GRAPH_BUFFER_DEG
    buffered = (west - buf, south - buf, east + buf, north + buf)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(buffered, cache_dir)
    if cache_file.exists():
        return ox.load_graphml(cache_file)
    try:
        graph = ox.graph_from_bbox(buffered, network_type="drive")
    except Exception as exc:  # noqa: BLE001 -- osmnx raises several exception types
        raise RouteGraphError(f"Road graph fetch failed: {exc}") from exc
    ox.save_graphml(graph, cache_file)
    return graph


def _nearest_hospital(centroid_lat: float, centroid_lon: float, hospitals: list) -> Optional[dict]:
    if not hospitals:
        return None
    return min(
        hospitals,
        key=lambda h: (h["lat"] - centroid_lat) ** 2 + (h["lon"] - centroid_lon) ** 2,
    )


def _shortest_len(graph: nx.MultiDiGraph, u, v) -> Optional[float]:
    try:
        return nx.shortest_path_length(graph, u, v, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def _edges_gdf(graph: nx.MultiDiGraph):
    """Graph edges as a GeoDataFrame (u, v, key, geometry), EPSG:4326 --
    the single source of truth for "does this polygon touch this road",
    shared by the bulk pipeline step and the on-demand route endpoint so
    the two can never disagree on a borderline/boundary-touching case."""
    import geopandas as gpd

    return gpd.GeoDataFrame(ox.graph_to_gdfs(graph, nodes=False)[["geometry"]]).reset_index()


def _edge_keys_for_geometry(edges_gdf, geometry, geometry_crs) -> list:
    """(u, v, key) tuples for edges in edges_gdf (EPSG:4326) intersecting
    one geometry given in geometry_crs."""
    import geopandas as gpd

    geom_4326 = gpd.GeoSeries([geometry], crs=geometry_crs).to_crs(edges_gdf.crs).iloc[0]
    hits = edges_gdf[edges_gdf.intersects(geom_4326)]
    return list(zip(hits["u"], hits["v"], hits["key"]))


def _evaluate(graph: nx.MultiDiGraph, orig_node, dest_node, edge_keys: list) -> dict:
    before_len = _shortest_len(graph, orig_node, dest_node)
    if before_len is None:
        return {"route_impact": "unknown", "detour_m": None}

    removed = []
    for u, v, k in edge_keys:
        if graph.has_edge(u, v, k):
            removed.append((u, v, k, dict(graph[u][v][k])))
            graph.remove_edge(u, v, k)
    try:
        after_len = _shortest_len(graph, orig_node, dest_node)
    finally:
        for u, v, k, data in removed:
            graph.add_edge(u, v, key=k, **data)

    if after_len is None:
        return {"route_impact": "no_alternative", "detour_m": None, "before_m": before_len}
    if after_len > before_len + 1.0:
        return {
            "route_impact": "detour",
            "detour_m": round(after_len - before_len, 1),
            "before_m": before_len,
            "after_m": after_len,
        }
    return {"route_impact": "none", "detour_m": 0.0, "before_m": before_len, "after_m": after_len}


def _polygons_edge_keys(edges_gdf, kept_polygons: list) -> dict:
    """Vectorized (geopandas sjoin, not a per-polygon Python loop over
    every edge) -- {polygon_index: [(u,v,key), ...]} for polygons that
    intersect at least one road edge. Uses the same edges_gdf (and hence
    the same intersects() predicate/CRS path) as the on-demand single-
    polygon lookup, so the two never disagree."""
    import geopandas as gpd

    area_crs = kept_polygons[0].area_crs
    polys_gdf = gpd.GeoDataFrame(
        {"idx": range(len(kept_polygons))},
        geometry=[p.geometry for p in kept_polygons],
        crs=area_crs,
    ).to_crs(edges_gdf.crs)
    joined = gpd.sjoin(polys_gdf, edges_gdf, predicate="intersects", how="inner")
    out: dict = {}
    for idx, u, v, k in zip(joined["idx"], joined["u"], joined["v"], joined["key"]):
        out.setdefault(idx, []).append((u, v, k))
    return out


def compute_route_impacts(kept_polygons: list, facilities: dict, bounds_4326: tuple) -> None:
    """Mutates route_impact/detour_m on each kept polygon that intersects
    a road. Polygons that don't touch any road are left at the
    PolygonResult default (None -- "not applicable", distinct from the
    computed "none"). Raises RouteGraphError if the road graph can't be
    fetched at all -- callers should catch this and mark affected
    polygons "unknown" rather than crash the whole analysis."""
    if not kept_polygons:
        return
    hospitals = facilities.get("hospitals", [])
    graph = get_road_graph(bounds_4326, _cache_dir())

    edge_keys_by_idx = _polygons_edge_keys(_edges_gdf(graph), kept_polygons)
    for idx, edge_keys in edge_keys_by_idx.items():
        p = kept_polygons[idx]
        hospital = _nearest_hospital(p.centroid_lat, p.centroid_lon, hospitals)
        if hospital is None:
            p.route_impact = "unknown"
            continue
        try:
            orig_node = ox.distance.nearest_nodes(graph, X=p.centroid_lon, Y=p.centroid_lat)
            dest_node = ox.distance.nearest_nodes(graph, X=hospital["lon"], Y=hospital["lat"])
        except Exception:  # noqa: BLE001
            p.route_impact = "unknown"
            continue

        result = _evaluate(graph, orig_node, dest_node, edge_keys)
        p.route_impact = result["route_impact"]
        p.detour_m = result["detour_m"]


def _cache_dir() -> Path:
    from app.db import ROUTE_GRAPH_CACHE_DIR

    return ROUTE_GRAPH_CACHE_DIR


def _path_coords(graph: nx.MultiDiGraph, path: list) -> list:
    return [[graph.nodes[n]["x"], graph.nodes[n]["y"]] for n in path]


def get_route_for_polygon(
    polygon_geom_4326,
    centroid_lat: float,
    centroid_lon: float,
    facilities: dict,
    bounds_4326: tuple,
) -> dict:
    """On-demand (not run for every polygon up front): returns the
    original and detour route geometries for the map to draw when a
    polygon is selected. {status, route_impact, detour_m, hospital_name,
    original_path (GeoJSON LineString coords or None), detour_path
    (GeoJSON LineString coords or None, same as original_path when
    route_impact == "none")}."""
    hospitals = facilities.get("hospitals", [])
    hospital = _nearest_hospital(centroid_lat, centroid_lon, hospitals)
    if hospital is None:
        return {
            "status": "unknown",
            "route_impact": "unknown",
            "detour_m": None,
            "reason": "No hospital data for this scene.",
        }

    try:
        graph = get_road_graph(bounds_4326, _cache_dir())
    except RouteGraphError as exc:
        return {"status": "unknown", "route_impact": "unknown", "detour_m": None, "reason": str(exc)}

    edge_keys = _edge_keys_for_geometry(_edges_gdf(graph), polygon_geom_4326, "EPSG:4326")
    try:
        orig_node = ox.distance.nearest_nodes(graph, X=centroid_lon, Y=centroid_lat)
        dest_node = ox.distance.nearest_nodes(graph, X=hospital["lon"], Y=hospital["lat"])
    except Exception:  # noqa: BLE001
        return {
            "status": "unknown",
            "route_impact": "unknown",
            "detour_m": None,
            "reason": "Could not snap to the road graph.",
        }

    try:
        original_path = nx.shortest_path(graph, orig_node, dest_node, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {
            "status": "ok",
            "route_impact": "unknown",
            "detour_m": None,
            "hospital_name": hospital.get("name"),
            "original_path": None,
            "detour_path": None,
            "reason": "No route to the nearest hospital exists even before removing this road.",
        }

    if not edge_keys:
        return {
            "status": "ok",
            "route_impact": "none",
            "detour_m": 0.0,
            "hospital_name": hospital.get("name"),
            "original_path": _path_coords(graph, original_path),
            "detour_path": None,
        }

    removed = []
    for u, v, k in edge_keys:
        if graph.has_edge(u, v, k):
            removed.append((u, v, k, dict(graph[u][v][k])))
            graph.remove_edge(u, v, k)
    try:
        detour_path = nx.shortest_path(graph, orig_node, dest_node, weight="length")
        detour_len = nx.shortest_path_length(graph, orig_node, dest_node, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        detour_path = None
        detour_len = None
    finally:
        for u, v, k, data in removed:
            graph.add_edge(u, v, key=k, **data)

    original_len = nx.shortest_path_length(graph, orig_node, dest_node, weight="length")

    if detour_path is None:
        route_impact, detour_m = "no_alternative", None
    elif detour_len > original_len + 1.0:
        route_impact, detour_m = "detour", round(detour_len - original_len, 1)
    else:
        route_impact, detour_m = "none", 0.0

    return {
        "status": "ok",
        "route_impact": route_impact,
        "detour_m": detour_m,
        "hospital_name": hospital.get("name"),
        "original_path": _path_coords(graph, original_path),
        "detour_path": _path_coords(graph, detour_path) if detour_path else None,
    }
