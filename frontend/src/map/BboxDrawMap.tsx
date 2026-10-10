import { useEffect, useRef, useState } from "react";
import { Map as MLMap, type GeoJSONSource, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export type Bbox = [number, number, number, number]; // west, south, east, north

function toBbox(a: [number, number], b: [number, number]): Bbox {
  return [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])];
}

export default function BboxDrawMap({ onBboxChange }: { onBboxChange: (bbox: Bbox | null) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const firstCornerRef = useRef<[number, number] | null>(null);
  const [hint, setHint] = useState("Click to place the first corner");

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new MLMap({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [79, 22],
      zoom: 3.6,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      map.addSource("bbox-draw", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "bbox-draw-fill",
        type: "fill",
        source: "bbox-draw",
        paint: { "fill-color": "#2FD3C1", "fill-opacity": 0.15 },
      });
      map.addLayer({
        id: "bbox-draw-line",
        type: "line",
        source: "bbox-draw",
        paint: { "line-color": "#2FD3C1", "line-width": 2, "line-dasharray": [2, 1] },
      });
    });

    function setRect(a: [number, number], b: [number, number]) {
      const [west, south, east, north] = toBbox(a, b);
      const source = map.getSource("bbox-draw") as GeoJSONSource | undefined;
      source?.setData({
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: {},
            geometry: {
              type: "Polygon",
              coordinates: [
                [
                  [west, south],
                  [east, south],
                  [east, north],
                  [west, north],
                  [west, south],
                ],
              ],
            },
          },
        ],
      });
    }

    map.on("click", (e) => {
      const lngLat: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      if (!firstCornerRef.current) {
        firstCornerRef.current = lngLat;
        setHint("Click to place the opposite corner");
      } else {
        setRect(firstCornerRef.current, lngLat);
        const bbox = toBbox(firstCornerRef.current, lngLat);
        onBboxChange(bbox);
        setHint("Area set — click again to redraw");
        firstCornerRef.current = null;
      }
    });

    map.on("mousemove", (e) => {
      if (!firstCornerRef.current) return;
      setRect(firstCornerRef.current, [e.lngLat.lng, e.lngLat.lat]);
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ position: "relative" }}>
      <div
        ref={containerRef}
        style={{ width: "100%", height: "260px", borderRadius: "var(--radius-sm)", overflow: "hidden" }}
      />
      <div
        style={{
          position: "absolute",
          top: "8px",
          left: "8px",
          background: "rgba(11,18,21,0.75)",
          color: "var(--color-text)",
          fontSize: "11px",
          padding: "4px 8px",
          borderRadius: "4px",
          pointerEvents: "none",
        }}
      >
        {hint}
      </div>
    </div>
  );
}
