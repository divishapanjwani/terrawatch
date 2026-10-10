import { useEffect, useRef, useState } from "react";
import {
  Map as MLMap,
  type StyleSpecification,
  type MapGeoJSONFeature,
  type GeoJSONSource,
  type FilterSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Feature, FeatureCollection } from "geojson";
import type { Bounds, FacilitiesData } from "../api/client";

const FACILITY_COLOR_EXPR = [
  "match",
  ["get", "category"],
  "hospital",
  "#E5484D",
  "school",
  "#2FD3C1",
  "shelter",
  "#F5A524",
  "#8FA3A8",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
] as any;

function facilitiesToGeoJSON(facilities: FacilitiesData): {
  points: FeatureCollection;
  lines: FeatureCollection;
} {
  const points: Feature[] = [
    ...facilities.hospitals.map((f) => ({
      type: "Feature" as const,
      properties: { category: "hospital", name: f.name },
      geometry: { type: "Point" as const, coordinates: [f.lon, f.lat] },
    })),
    ...facilities.schools.map((f) => ({
      type: "Feature" as const,
      properties: { category: "school", name: f.name },
      geometry: { type: "Point" as const, coordinates: [f.lon, f.lat] },
    })),
    ...facilities.shelters.map((f) => ({
      type: "Feature" as const,
      properties: { category: "shelter", name: f.name },
      geometry: { type: "Point" as const, coordinates: [f.lon, f.lat] },
    })),
  ];
  const lines: Feature[] = facilities.roads.map((r) => ({
    type: "Feature" as const,
    properties: { name: r.name, highway: r.highway },
    geometry: { type: "LineString" as const, coordinates: r.coords },
  }));
  return {
    points: { type: "FeatureCollection", features: points },
    lines: { type: "FeatureCollection", features: lines },
  };
}

function addFacilitiesLayers(map: MLMap, facilities: FacilitiesData) {
  const { points, lines } = facilitiesToGeoJSON(facilities);
  if (map.getSource("facility-points")) {
    (map.getSource("facility-points") as GeoJSONSource).setData(points);
    (map.getSource("facility-lines") as GeoJSONSource).setData(lines);
    return;
  }
  map.addSource("facility-points", { type: "geojson", data: points });
  map.addSource("facility-lines", { type: "geojson", data: lines });

  map.addLayer({
    id: "roads-line",
    type: "line",
    source: "facility-lines",
    layout: { visibility: "none" },
    paint: { "line-color": "#8FA3A8", "line-width": 1.5, "line-opacity": 0.7 },
  });

  map.addLayer({
    id: "facility-points-circle",
    type: "circle",
    source: "facility-points",
    layout: { visibility: "none" },
    paint: {
      "circle-radius": 4,
      "circle-color": FACILITY_COLOR_EXPR,
      "circle-stroke-width": 1,
      "circle-stroke-color": "#ffffff",
    },
  });
}

function mapHasImage(map: MLMap): boolean {
  // Each map's own image source is named differently ("before-img" for the
  // before map, "after-img" for the after map) -- check both.
  return Boolean(map.getSource("before-img") || map.getSource("after-img"));
}

function setLayerVisibility(map: MLMap, layerId: string, visible: boolean) {
  if (map.getLayer(layerId)) map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
}

function addPopulationLayer(map: MLMap, url: string, bounds: Bounds) {
  if (map.getSource("population-img")) return;
  map.addSource("population-img", { type: "image", url, coordinates: boundsToCoords(bounds) });
  map.addLayer({
    id: "population-layer",
    type: "raster",
    source: "population-img",
    layout: { visibility: "none" },
    paint: { "raster-opacity": 1 },
  });
}

const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: "bg",
      type: "background",
      paint: { "background-color": "#0b1215" },
    },
  ],
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SEVERITY_COLOR_EXPR: any = [
  "match",
  ["get", "severity"],
  "High",
  "#E5484D",
  "Medium",
  "#F5A524",
  "Low",
  "#F2D45C",
  "#6B7D82",
];

// Flattens a Polygon/MultiPolygon's coordinates into a [west, south, east,
// north] bbox -- no turf dependency needed for this one lookup.
function geometryBbox(geometry: GeoJSON.Geometry): [number, number, number, number] | null {
  let west = Infinity,
    south = Infinity,
    east = -Infinity,
    north = -Infinity;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const visit = (coords: any): void => {
    if (typeof coords[0] === "number") {
      const [x, y] = coords;
      west = Math.min(west, x);
      east = Math.max(east, x);
      south = Math.min(south, y);
      north = Math.max(north, y);
    } else {
      coords.forEach(visit);
    }
  };
  if ("coordinates" in geometry) visit(geometry.coordinates);
  if (!Number.isFinite(west)) return null;
  return [west, south, east, north];
}

function boundsToCoords(b: Bounds): [[number, number], [number, number], [number, number], [number, number]] {
  return [
    [b.west, b.north],
    [b.east, b.north],
    [b.east, b.south],
    [b.west, b.south],
  ];
}

const NICE_SCALE_DISTANCES_M = [
  5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000,
];

function computeScaleBar(zoom: number, lat: number, maxWidthPx = 100): { widthPx: number; label: string } {
  const metersPerPixel = (156543.03392 * Math.cos((lat * Math.PI) / 180)) / Math.pow(2, zoom);
  let chosen = NICE_SCALE_DISTANCES_M[0];
  for (const d of NICE_SCALE_DISTANCES_M) {
    if (d / metersPerPixel <= maxWidthPx) chosen = d;
    else break;
  }
  const widthPx = chosen / metersPerPixel;
  const label = chosen >= 1000 ? `${chosen / 1000} km` : `${chosen} m`;
  return { widthPx, label };
}

export interface RouteDisplay {
  routeImpact: string;
  originalPath: [number, number][] | null;
  detourPath: [number, number][] | null;
}

interface Props {
  beforeUrl: string;
  afterUrl: string;
  bounds: Bounds;
  geojson?: FeatureCollection | null;
  selectedId?: string | null;
  zoomToId?: string | null;
  hoveredId?: string | null;
  onPolygonClick?: (feature: MapGeoJSONFeature) => void;
  onPolygonHover?: (id: string | null) => void;
  showRejected?: boolean;
  beforeLabel?: string;
  afterLabel?: string;
  facilities?: FacilitiesData | null;
  showFacilities?: boolean;
  showRoads?: boolean;
  populationUrl?: string | null;
  showPopulation?: boolean;
  drawMode?: boolean;
  onDrawComplete?: (polygon: GeoJSON.Polygon | null) => void;
  hazardZone?: GeoJSON.Polygon | null;
  route?: RouteDisplay | null;
}

const ROUTE_ORIGINAL_COLOR: Record<string, string> = {
  none: "#2FD3C1",
  detour: "#F5A524",
  no_alternative: "#E5484D",
  unknown: "#8FA3A8",
};

function addRouteLayers(map: MLMap) {
  if (map.getSource("route-original")) return;
  map.addSource("route-original", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addSource("route-detour", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({
    id: "route-original-line",
    type: "line",
    source: "route-original",
    paint: {
      "line-color": ["get", "color"],
      "line-width": 3.5,
      "line-dasharray": ["case", ["==", ["get", "cut"], true], ["literal", [2, 1.5]], ["literal", [1, 0]]],
    },
  });
  map.addLayer({
    id: "route-detour-line",
    type: "line",
    source: "route-detour",
    paint: { "line-color": "#F5A524", "line-width": 3.5, "line-dasharray": [1, 1.5] },
  });
}

function setRouteData(map: MLMap, route: RouteDisplay | null) {
  const origSource = map.getSource("route-original") as GeoJSONSource | undefined;
  const detourSource = map.getSource("route-detour") as GeoJSONSource | undefined;
  if (!origSource || !detourSource) return;
  if (!route || !route.originalPath) {
    origSource.setData({ type: "FeatureCollection", features: [] });
    detourSource.setData({ type: "FeatureCollection", features: [] });
    return;
  }
  const color = ROUTE_ORIGINAL_COLOR[route.routeImpact] ?? ROUTE_ORIGINAL_COLOR.unknown;
  origSource.setData({
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { color, cut: route.routeImpact === "no_alternative" },
        geometry: { type: "LineString", coordinates: route.originalPath },
      },
    ],
  });
  detourSource.setData({
    type: "FeatureCollection",
    features: route.detourPath
      ? [
          {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: route.detourPath },
          },
        ]
      : [],
  });
}

function addHazardZoneLayers(map: MLMap) {
  if (map.getSource("hazard-zone")) return;
  map.addSource("hazard-zone", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({
    id: "hazard-zone-fill",
    type: "fill",
    source: "hazard-zone",
    paint: { "fill-color": "#E5484D", "fill-opacity": 0.12 },
  });
  map.addLayer({
    id: "hazard-zone-line",
    type: "line",
    source: "hazard-zone",
    paint: { "line-color": "#E5484D", "line-width": 2, "line-dasharray": [2, 1] },
  });
}

function setHazardZoneData(map: MLMap, points: [number, number][], closed: boolean) {
  const source = map.getSource("hazard-zone") as GeoJSONSource | undefined;
  if (!source) return;
  if (points.length < 2) {
    source.setData({ type: "FeatureCollection", features: [] });
    return;
  }
  const geometry: GeoJSON.Geometry = closed
    ? { type: "Polygon", coordinates: [[...points, points[0]]] }
    : { type: "LineString", coordinates: points };
  source.setData({ type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry }] });
}

const KEPT_FILTER = ["==", ["get", "status"], "kept"] as unknown as FilterSpecification;
const REJECTED_FILTER = ["==", ["get", "status"], "rejected"] as unknown as FilterSpecification;
const NEEDS_REVIEW_FILTER = [
  "all",
  ["==", ["get", "status"], "kept"],
  ["==", ["get", "needs_review"], true],
] as unknown as FilterSpecification;

function addPolygonLayers(map: MLMap, geojson: FeatureCollection) {
  if (map.getSource("changes")) {
    (map.getSource("changes") as GeoJSONSource).setData(geojson);
    return;
  }
  map.addSource("changes", { type: "geojson", data: geojson });

  // Kept changes: filled, colored by severity.
  map.addLayer({
    id: "changes-fill",
    type: "fill",
    source: "changes",
    filter: KEPT_FILTER,
    paint: {
      "fill-color": SEVERITY_COLOR_EXPR,
      "fill-opacity": 0.3,
    },
  });
  map.addLayer({
    id: "changes-line",
    type: "line",
    source: "changes",
    filter: KEPT_FILTER,
    paint: {
      "line-color": SEVERITY_COLOR_EXPR,
      "line-width": 1.8,
    },
  });

  // Needs-review kept changes: dotted outline overlay.
  map.addLayer({
    id: "changes-needs-review",
    type: "line",
    source: "changes",
    filter: NEEDS_REVIEW_FILTER,
    paint: {
      "line-color": "#E6EDEF",
      "line-width": 1.5,
      "line-dasharray": [1, 2],
    },
  });

  // Rejected changes: grey dashed outline, hidden by default (toggled by
  // the "Show rejected changes" control).
  map.addLayer({
    id: "changes-rejected",
    type: "line",
    source: "changes",
    filter: REJECTED_FILTER,
    layout: { visibility: "none" },
    paint: {
      "line-color": "#6B7D82",
      "line-width": 1.5,
      "line-dasharray": [3, 2],
    },
  });
  map.addLayer({
    id: "changes-rejected-fill",
    type: "fill",
    source: "changes",
    filter: REJECTED_FILTER,
    layout: { visibility: "none" },
    paint: {
      "fill-color": "#6B7D82",
      "fill-opacity": 0.12,
    },
  });

  // Hover glow: a soft, wide, translucent halo underneath a crisp accent
  // line -- gives the "polygon hover glow" the brief asks for without any
  // raster/SVG filter trickery.
  map.addLayer({
    id: "changes-hover-glow",
    type: "line",
    source: "changes",
    filter: ["==", ["get", "id"], "__none__"],
    paint: {
      "line-color": "#2FD3C1",
      "line-width": 10,
      "line-blur": 6,
      "line-opacity": 0.5,
    },
  });
  map.addLayer({
    id: "changes-hover",
    type: "line",
    source: "changes",
    filter: ["==", ["get", "id"], "__none__"],
    paint: {
      "line-color": "#2FD3C1",
      "line-width": 2.5,
    },
  });

  map.addLayer({
    id: "changes-selected",
    type: "line",
    source: "changes",
    filter: ["==", ["get", "id"], "__none__"],
    paint: {
      "line-color": "#E6EDEF",
      "line-width": 3,
    },
  });
}

function setRejectedVisibility(map: MLMap, visible: boolean) {
  const v = visible ? "visible" : "none";
  for (const id of ["changes-rejected", "changes-rejected-fill"]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", v);
  }
}

export default function CompareMap({
  beforeUrl,
  afterUrl,
  bounds,
  geojson,
  selectedId,
  zoomToId,
  hoveredId,
  onPolygonClick,
  onPolygonHover,
  showRejected = false,
  beforeLabel = "Before",
  afterLabel = "After",
  facilities,
  showFacilities = false,
  showRoads = false,
  populationUrl,
  showPopulation = false,
  drawMode = false,
  onDrawComplete,
  hazardZone,
  route,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const beforeDivRef = useRef<HTMLDivElement>(null);
  const afterDivRef = useRef<HTMLDivElement>(null);
  const clipDivRef = useRef<HTMLDivElement>(null);
  const [sliderPct, setSliderPct] = useState(50);
  const [containerWidth, setContainerWidth] = useState(0);
  const draggingRef = useRef(false);
  const mapsRef = useRef<{ before: MLMap; after: MLMap } | null>(null);
  const geojsonRef = useRef(geojson);
  const onClickRef = useRef(onPolygonClick);
  const onHoverRef = useRef(onPolygonHover);
  const showRejectedRef = useRef(showRejected);
  const facilitiesRef = useRef(facilities);
  const showFacilitiesRef = useRef(showFacilities);
  const showRoadsRef = useRef(showRoads);
  const populationUrlRef = useRef(populationUrl);
  const showPopulationRef = useRef(showPopulation);
  const drawModeRef = useRef(drawMode);
  const routeRef = useRef(route);
  routeRef.current = route;
  const [drawPoints, setDrawPoints] = useState<[number, number][]>([]);
  const [cursorLngLat, setCursorLngLat] = useState<{ lng: number; lat: number } | null>(null);
  const [viewState, setViewState] = useState({ zoom: 12, lat: 0 });
  geojsonRef.current = geojson;
  onClickRef.current = onPolygonClick;
  onHoverRef.current = onPolygonHover;
  showRejectedRef.current = showRejected;
  facilitiesRef.current = facilities;
  showFacilitiesRef.current = showFacilities;
  showRoadsRef.current = showRoads;
  populationUrlRef.current = populationUrl;
  showPopulationRef.current = showPopulation;
  drawModeRef.current = drawMode;

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const observer = new ResizeObserver((entries) => {
      setContainerWidth(entries[0].contentRect.width);
    });
    observer.observe(el);
    setContainerWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!beforeDivRef.current || !afterDivRef.current) return;

    const afterMap = new MLMap({
      container: afterDivRef.current,
      style: BASE_STYLE,
      bounds: [
        [bounds.west, bounds.south],
        [bounds.east, bounds.north],
      ],
      attributionControl: false,
    });

    const beforeMap = new MLMap({
      container: beforeDivRef.current,
      style: BASE_STYLE,
      bounds: [
        [bounds.west, bounds.south],
        [bounds.east, bounds.north],
      ],
      attributionControl: false,
    });

    const addImage = (map: MLMap, id: string, url: string) => {
      const onLoad = () => {
        if (map.getSource(id)) return;
        map.addSource(id, {
          type: "image",
          url,
          coordinates: boundsToCoords(bounds),
        });
        map.addLayer({
          id: `${id}-layer`,
          type: "raster",
          source: id,
          paint: { "raster-opacity": 1 },
        });
        if (geojsonRef.current) {
          addPolygonLayers(map, geojsonRef.current);
          setRejectedVisibility(map, showRejectedRef.current);
        }
        if (facilitiesRef.current) {
          addFacilitiesLayers(map, facilitiesRef.current);
          setLayerVisibility(map, "facility-points-circle", showFacilitiesRef.current);
          setLayerVisibility(map, "roads-line", showRoadsRef.current);
        }
        if (populationUrlRef.current) {
          addPopulationLayer(map, populationUrlRef.current, bounds);
          setLayerVisibility(map, "population-layer", showPopulationRef.current);
        }
        addHazardZoneLayers(map);
        addRouteLayers(map);
        setRouteData(map, routeRef.current ?? null);
      };
      if (map.isStyleLoaded()) onLoad();
      else map.on("load", onLoad);

      for (const layerId of ["changes-fill", "changes-rejected-fill"]) {
        map.on("click", layerId, (e) => {
          if (drawModeRef.current) return;
          if (e.features && e.features[0]) onClickRef.current?.(e.features[0]);
        });
        map.on("mouseenter", layerId, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mousemove", layerId, (e) => {
          if (e.features && e.features[0]) onHoverRef.current?.(String(e.features[0].properties?.id));
        });
        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
          onHoverRef.current?.(null);
        });
      }
    };

    addImage(afterMap, "after-img", afterUrl);
    addImage(beforeMap, "before-img", beforeUrl);

    for (const map of [afterMap, beforeMap]) {
      map.on("click", (e) => {
        if (!drawModeRef.current) return;
        const { lng, lat } = map.unproject(e.point);
        setDrawPoints((prev) => [...prev, [lng, lat]]);
      });
    }

    let syncing = false;
    const sync = (src: MLMap, dst: MLMap) => () => {
      if (syncing) return;
      syncing = true;
      dst.jumpTo({
        center: src.getCenter(),
        zoom: src.getZoom(),
        bearing: src.getBearing(),
        pitch: src.getPitch(),
      });
      syncing = false;
    };
    afterMap.on("move", sync(afterMap, beforeMap));
    beforeMap.on("move", sync(beforeMap, afterMap));

    // Registered on both maps -- the swipe divider means the cursor can be
    // over either one depending on slider position.
    for (const map of [afterMap, beforeMap]) {
      map.on("mousemove", (e) => setCursorLngLat(e.lngLat));
      map.on("mouseout", () => setCursorLngLat(null));
    }
    const updateViewState = () => setViewState({ zoom: afterMap.getZoom(), lat: afterMap.getCenter().lat });
    afterMap.on("move", updateViewState);
    updateViewState();

    mapsRef.current = { before: beforeMap, after: afterMap };

    return () => {
      afterMap.remove();
      beforeMap.remove();
      mapsRef.current = null;
    };
  }, [beforeUrl, afterUrl, bounds]);

  useEffect(() => {
    if (!mapsRef.current || !geojson) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (mapHasImage(map)) {
        addPolygonLayers(map, geojson);
        setRejectedVisibility(map, showRejected);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      setRejectedVisibility(map, showRejected);
    }
  }, [showRejected]);

  useEffect(() => {
    if (!mapsRef.current || !facilities) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (mapHasImage(map)) {
        addFacilitiesLayers(map, facilities);
        setLayerVisibility(map, "facility-points-circle", showFacilities);
        setLayerVisibility(map, "roads-line", showRoads);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facilities]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (mapHasImage(map)) setRouteData(map, route ?? null);
    }
  }, [route]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      setLayerVisibility(map, "facility-points-circle", showFacilities);
    }
  }, [showFacilities]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      setLayerVisibility(map, "roads-line", showRoads);
    }
  }, [showRoads]);

  useEffect(() => {
    if (!mapsRef.current || !populationUrl) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (mapHasImage(map)) {
        addPopulationLayer(map, populationUrl, bounds);
        setLayerVisibility(map, "population-layer", showPopulation);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [populationUrl]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      setLayerVisibility(map, "population-layer", showPopulation);
    }
  }, [showPopulation]);

  useEffect(() => {
    if (!drawMode) setDrawPoints([]);
  }, [drawMode]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (map.getSource("hazard-zone")) setHazardZoneData(map, drawPoints, false);
    }
  }, [drawPoints]);

  useEffect(() => {
    if (!mapsRef.current || drawMode) return; // drawing in progress takes precedence
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (!map.getSource("hazard-zone")) continue;
      if (hazardZone) {
        setHazardZoneData(map, hazardZone.coordinates[0].slice(0, -1) as [number, number][], true);
      } else {
        setHazardZoneData(map, [], false);
      }
    }
  }, [hazardZone, drawMode]);

  function finishDrawing() {
    if (drawPoints.length < 3) return;
    onDrawComplete?.({ type: "Polygon", coordinates: [[...drawPoints, drawPoints[0]]] });
    setDrawPoints([]);
  }

  function cancelDrawing() {
    onDrawComplete?.(null);
    setDrawPoints([]);
  }

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (map.getLayer("changes-selected")) {
        map.setFilter("changes-selected", ["==", ["get", "id"], selectedId ?? "__none__"]);
      }
    }
  }, [selectedId]);

  useEffect(() => {
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      const filter = ["==", ["get", "id"], hoveredId ?? "__none__"] as unknown as FilterSpecification;
      if (map.getLayer("changes-hover")) map.setFilter("changes-hover", filter);
      if (map.getLayer("changes-hover-glow")) map.setFilter("changes-hover-glow", filter);
    }
  }, [hoveredId]);

  useEffect(() => {
    if (!mapsRef.current || !geojson || !zoomToId) return;
    const feature = geojson.features.find((f) => String(f.properties?.id) === zoomToId);
    if (!feature) return;
    const bbox = geometryBbox(feature.geometry);
    if (!bbox) return;
    const [west, south, east, north] = bbox;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      map.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        { padding: 80, maxZoom: 17, duration: 600 },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zoomToId]);

  useEffect(() => {
    if (clipDivRef.current) {
      clipDivRef.current.style.width = `${sliderPct}%`;
    }
  }, [sliderPct]);

  useEffect(() => {
    if (!mapsRef.current) return;
    mapsRef.current.before.resize();
    mapsRef.current.after.resize();
  }, [containerWidth]);

  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
      const pct = ((clientX - rect.left) / rect.width) * 100;
      setSliderPct(Math.min(100, Math.max(0, pct)));
    };
    const onUp = () => {
      draggingRef.current = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("touchmove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("touchend", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("touchmove", onMove);
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("touchend", onUp);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <div ref={afterDivRef} style={{ position: "absolute", inset: 0 }} />
      <div
        ref={clipDivRef}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          bottom: 0,
          width: "50%",
          overflow: "hidden",
        }}
      >
        <div
          ref={beforeDivRef}
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            bottom: 0,
            width: containerWidth ? `${containerWidth}px` : "100%",
          }}
        />
      </div>

      <div
        onMouseDown={() => (draggingRef.current = true)}
        onTouchStart={() => (draggingRef.current = true)}
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: `${sliderPct}%`,
          width: "2px",
          marginLeft: "-1px",
          background: "var(--color-accent)",
          boxShadow: "0 0 8px rgba(47,211,193,0.6)",
          cursor: "ew-resize",
          zIndex: 10,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "26px",
            height: "26px",
            borderRadius: "50%",
            background: "var(--color-accent)",
            color: "#06201c",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            fontWeight: 700,
            boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
          }}
        >
          &#8596;
        </div>
      </div>

      <div
        className="ts-float"
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          padding: "5px 10px",
          fontSize: "var(--font-size-xs)",
          zIndex: 5,
          fontWeight: 500,
        }}
      >
        {beforeLabel}
      </div>
      <div
        className="ts-float"
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          padding: "5px 10px",
          fontSize: "var(--font-size-xs)",
          zIndex: 5,
          fontWeight: 500,
        }}
      >
        {afterLabel}
      </div>

      <Legend showRejected={showRejected} />

      <div
        style={{
          position: "absolute",
          bottom: 12,
          right: 12,
          zIndex: 5,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          gap: "8px",
        }}
      >
        <div
          className="ts-float"
          style={{
            padding: "6px 10px",
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-end",
            gap: "4px",
          }}
        >
          <div
            style={{
              width: `${computeScaleBar(viewState.zoom, viewState.lat).widthPx}px`,
              borderBottom: "2px solid var(--color-text-secondary)",
              borderLeft: "2px solid var(--color-text-secondary)",
              borderRight: "2px solid var(--color-text-secondary)",
              height: "5px",
            }}
          />
          <span className="mono" style={{ fontSize: "10px", color: "var(--color-text-secondary)" }}>
            {computeScaleBar(viewState.zoom, viewState.lat).label}
          </span>
        </div>
        {cursorLngLat && (
          <div
            className="ts-float mono"
            style={{ padding: "4px 8px", fontSize: "10px", color: "var(--color-text-secondary)" }}
          >
            {cursorLngLat.lat.toFixed(5)}, {cursorLngLat.lng.toFixed(5)}
          </div>
        )}
      </div>

      <div
        style={{
          position: "absolute",
          top: 52,
          right: 12,
          zIndex: 5,
          display: "flex",
          flexDirection: "column",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
        }}
        className="ts-float"
      >
        <button
          onClick={() => mapsRef.current?.after.zoomIn({ duration: 200 })}
          aria-label="Zoom in"
          style={{
            width: "28px",
            height: "28px",
            border: "none",
            borderBottom: "1px solid var(--color-border)",
            background: "transparent",
            color: "var(--color-text)",
            cursor: "pointer",
            fontSize: "15px",
          }}
        >
          +
        </button>
        <button
          onClick={() => mapsRef.current?.after.zoomOut({ duration: 200 })}
          aria-label="Zoom out"
          style={{
            width: "28px",
            height: "28px",
            border: "none",
            background: "transparent",
            color: "var(--color-text)",
            cursor: "pointer",
            fontSize: "15px",
          }}
        >
          −
        </button>
      </div>

      {drawMode && (
        <div
          className="ts-float ts-fade-up"
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "8px 12px",
            fontSize: "var(--font-size-xs)",
            zIndex: 15,
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <span style={{ color: "var(--color-text-secondary)" }}>
            Click the map to add points (
            <span className="mono" style={{ color: "var(--color-text)" }}>
              {drawPoints.length}
            </span>{" "}
            so far). Need at least 3.
          </span>
          <button
            onClick={finishDrawing}
            disabled={drawPoints.length < 3}
            className="ts-btn ts-btn-primary ts-btn-sm"
          >
            Finish zone
          </button>
          <button onClick={cancelDrawing} className="ts-btn ts-btn-sm">
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

const SEVERITY_LEGEND: { label: string; color: string; pattern: string }[] = [
  { label: "High", color: "#E5484D", pattern: "solid" },
  { label: "Medium", color: "#F5A524", pattern: "solid" },
  { label: "Low", color: "#F2D45C", pattern: "solid" },
];

function Legend({ showRejected }: { showRejected: boolean }) {
  return (
    <div
      className="ts-float"
      title="Severity = change strength, not damage. sev_score = max(norm(log area_m²), norm(log change_magnitude)) — severe if very large OR very intense. High ≥ 0.66, Medium ≥ 0.33, else Low."
      style={{
        position: "absolute",
        bottom: 12,
        left: 12,
        padding: "10px 12px",
        fontSize: "var(--font-size-xs)",
        zIndex: 5,
        display: "flex",
        flexDirection: "column",
        gap: "5px",
        cursor: "help",
      }}
    >
      <div className="ts-label" style={{ marginBottom: "2px" }}>
        Severity
      </div>
      {SEVERITY_LEGEND.map(({ label, color }) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: "7px" }}>
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "2px",
              background: color,
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          <span style={{ color: "var(--color-text)" }}>{label}</span>
        </div>
      ))}
      <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
        <span
          style={{
            width: "14px",
            height: "0px",
            borderTop: "1.5px dotted var(--color-text)",
            display: "inline-block",
          }}
        />
        <span style={{ color: "var(--color-text)" }}>Needs review</span>
      </div>
      {showRejected && (
        <div style={{ display: "flex", alignItems: "center", gap: "7px" }}>
          <span
            style={{
              width: "14px",
              height: "0px",
              borderTop: "1.5px dashed var(--color-rejected)",
              display: "inline-block",
            }}
          />
          <span style={{ color: "var(--color-text)" }}>Rejected</span>
        </div>
      )}
    </div>
  );
}
