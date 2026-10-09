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
  "#C0392B",
  "school",
  "#2F5D46",
  "shelter",
  "#B8860B",
  "#5B6472",
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
] as any;

function facilitiesToGeoJSON(facilities: FacilitiesData): { points: FeatureCollection; lines: FeatureCollection } {
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
  return { points: { type: "FeatureCollection", features: points }, lines: { type: "FeatureCollection", features: lines } };
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
    paint: { "line-color": "#5B6472", "line-width": 1.5, "line-opacity": 0.85 },
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
      paint: { "background-color": "#e9e7e0" },
    },
  ],
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const SEVERITY_COLOR_EXPR: any = [
  "match",
  ["get", "severity"],
  "High",
  "#C0392B",
  "Medium",
  "#E67E22",
  "Low",
  "#F1C40F",
  "#8A8F98",
];

// Flattens a Polygon/MultiPolygon's coordinates into a [west, south, east,
// north] bbox -- no turf dependency needed for this one lookup.
function geometryBbox(geometry: GeoJSON.Geometry): [number, number, number, number] | null {
  let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
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
}

function addHazardZoneLayers(map: MLMap) {
  if (map.getSource("hazard-zone")) return;
  map.addSource("hazard-zone", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({
    id: "hazard-zone-fill",
    type: "fill",
    source: "hazard-zone",
    paint: { "fill-color": "#C0392B", "fill-opacity": 0.1 },
  });
  map.addLayer({
    id: "hazard-zone-line",
    type: "line",
    source: "hazard-zone",
    paint: { "line-color": "#C0392B", "line-width": 2, "line-dasharray": [2, 1] },
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
      "line-color": "#1F2328",
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
      "line-color": "#8A8F98",
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
      "fill-color": "#8A8F98",
      "fill-opacity": 0.12,
    },
  });

  map.addLayer({
    id: "changes-hover",
    type: "line",
    source: "changes",
    filter: ["==", ["get", "id"], "__none__"],
    paint: {
      "line-color": "#2F5D46",
      "line-width": 2.5,
    },
  });

  map.addLayer({
    id: "changes-selected",
    type: "line",
    source: "changes",
    filter: ["==", ["get", "id"], "__none__"],
    paint: {
      "line-color": "#1F2328",
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
  const [drawPoints, setDrawPoints] = useState<[number, number][]>([]);
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
      if (map.getLayer("changes-hover")) {
        map.setFilter("changes-hover", ["==", ["get", "id"], hoveredId ?? "__none__"]);
      }
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
        [[west, south], [east, north]],
        { padding: 80, maxZoom: 17, duration: 600 }
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
          width: "4px",
          marginLeft: "-2px",
          background: "var(--color-accent)",
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
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: "var(--color-accent)",
            color: "white",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
          }}
        >
          &#8596;
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          background: "rgba(255,255,255,0.9)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          padding: "4px 8px",
          fontSize: "var(--font-size-xs)",
          zIndex: 5,
        }}
      >
        {beforeLabel}
      </div>
      <div
        style={{
          position: "absolute",
          top: 12,
          right: 12,
          background: "rgba(255,255,255,0.9)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          padding: "4px 8px",
          fontSize: "var(--font-size-xs)",
          zIndex: 5,
        }}
      >
        {afterLabel}
      </div>

      <Legend showRejected={showRejected} />

      {drawMode && (
        <div
          style={{
            position: "absolute",
            top: 12,
            left: "50%",
            transform: "translateX(-50%)",
            background: "white",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            padding: "8px 12px",
            fontSize: "var(--font-size-xs)",
            zIndex: 15,
            display: "flex",
            alignItems: "center",
            gap: "10px",
            boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
          }}
        >
          <span>Click the map to add points ({drawPoints.length} so far). Need at least 3.</span>
          <button
            onClick={finishDrawing}
            disabled={drawPoints.length < 3}
            style={{
              padding: "4px 10px",
              fontSize: "var(--font-size-xs)",
              border: "none",
              borderRadius: "var(--radius-sm)",
              background: "var(--color-accent)",
              color: "white",
              cursor: drawPoints.length < 3 ? "not-allowed" : "pointer",
              opacity: drawPoints.length < 3 ? 0.5 : 1,
            }}
          >
            Finish zone
          </button>
          <button
            onClick={cancelDrawing}
            style={{
              padding: "4px 10px",
              fontSize: "var(--font-size-xs)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              background: "white",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

function Legend({ showRejected }: { showRejected: boolean }) {
  return (
    <div
      title="Severity = change strength, not damage. sev_score = 0.5·norm(area_m²) + 0.5·norm(change_magnitude). High ≥ 0.66, Medium ≥ 0.33, else Low."
      style={{
        position: "absolute",
        bottom: 12,
        left: 12,
        background: "rgba(255,255,255,0.95)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-sm)",
        padding: "8px 10px",
        fontSize: "var(--font-size-xs)",
        zIndex: 5,
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        cursor: "help",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: "2px" }}>Severity</div>
      {[
        ["High", "#C0392B"],
        ["Medium", "#E67E22"],
        ["Low", "#F1C40F"],
      ].map(([label, color]) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "2px",
              background: color,
              border: "1.5px solid rgba(0,0,0,0.3)",
              display: "inline-block",
            }}
          />
          <span>{label}</span>
        </div>
      ))}
      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        <span
          style={{
            width: "14px",
            height: "0px",
            borderTop: "1.5px dotted #1F2328",
            display: "inline-block",
          }}
        />
        <span>Needs review</span>
      </div>
      {showRejected && (
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span
            style={{
              width: "14px",
              height: "0px",
              borderTop: "1.5px dashed #8A8F98",
              display: "inline-block",
            }}
          />
          <span>Rejected</span>
        </div>
      )}
    </div>
  );
}
