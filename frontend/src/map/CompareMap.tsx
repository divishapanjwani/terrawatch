import { useEffect, useRef, useState } from "react";
import { Map as MLMap, type StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
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
  beforeLabel?: string;
  afterLabel?: string;
}

export default function CompareMap({
  beforeUrl,
  afterUrl,
  bounds,
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
      };
      if (map.isStyleLoaded()) onLoad();
      else map.on("load", onLoad);
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
    </div>
  );
}
