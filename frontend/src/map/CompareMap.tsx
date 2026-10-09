import { useEffect, useRef, useState } from "react";
import {
  Map as MLMap,
  type StyleSpecification,
  type MapGeoJSONFeature,
  type GeoJSONSource,
  type FilterSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import type { Bounds } from "../api/client";

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
  onPolygonClick?: (feature: MapGeoJSONFeature) => void;
  showRejected?: boolean;
  beforeLabel?: string;
  afterLabel?: string;
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
  onPolygonClick,
  showRejected = false,
  beforeLabel = "Before",
  afterLabel = "After",
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
  const showRejectedRef = useRef(showRejected);
  geojsonRef.current = geojson;
  onClickRef.current = onPolygonClick;
  showRejectedRef.current = showRejected;

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
      };
      if (map.isStyleLoaded()) onLoad();
      else map.on("load", onLoad);

      for (const layerId of ["changes-fill", "changes-rejected-fill"]) {
        map.on("click", layerId, (e) => {
          if (e.features && e.features[0]) onClickRef.current?.(e.features[0]);
        });
        map.on("mouseenter", layerId, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
        });
      }
    };

    addImage(afterMap, "after-img", afterUrl);
    addImage(beforeMap, "before-img", beforeUrl);

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
      if (map.isStyleLoaded() && map.getSource("before-img")) {
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
    if (!mapsRef.current) return;
    for (const map of [mapsRef.current.before, mapsRef.current.after]) {
      if (map.getLayer("changes-selected")) {
        map.setFilter("changes-selected", ["==", ["get", "id"], selectedId ?? "__none__"]);
      }
    }
  }, [selectedId]);

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
