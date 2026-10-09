import { useState } from "react";
import type { Feature, FeatureCollection } from "geojson";

const SEVERITY_COLOR: Record<string, string> = {
  High: "#C0392B",
  Medium: "#E67E22",
  Low: "#F1C40F",
};

const CHANGE_TYPE_LABEL: Record<string, string> = {
  new_construction: "New construction",
  structure_lost: "Structure lost",
  flooding: "Flooding",
  landslide_bare_soil: "Landslide / bare soil",
  vegetation_loss: "Vegetation loss",
  other: "Other / unclassified",
};

const SEVERITY_FILTERS = ["All", "High", "Medium", "Low"] as const;
type SeverityFilter = (typeof SEVERITY_FILTERS)[number];

const ROWS_PREVIEW = 10;

function nearestFacilityLabel(p: Record<string, unknown>): string {
  const hospM = p.nearest_hospital_m as number | null;
  const schoolM = p.nearest_school_m as number | null;
  const candidates: [number, string][] = [];
  if (hospM != null) candidates.push([hospM, "Hospital"]);
  if (schoolM != null) candidates.push([schoolM, "School"]);
  if (!candidates.length) return "—";
  candidates.sort((a, b) => a[0] - b[0]);
  const [dist, label] = candidates[0];
  return `${label} · ${dist.toLocaleString(undefined, { maximumFractionDigits: 0 })} m`;
}

export default function PriorityPanel({
  geojson,
  onSelect,
  hoveredId,
  onHoverRow,
}: {
  geojson: FeatureCollection;
  onSelect: (id: string) => void;
  hoveredId?: string | null;
  onHoverRow?: (id: string | null) => void;
}) {
  const [filter, setFilter] = useState<SeverityFilter>("All");
  const [showAll, setShowAll] = useState(false);

  const allRows = (geojson.features as Feature[])
    .filter((f) => f.properties?.status === "kept" && f.properties?.priority_rank != null)
    .sort((a, b) => Number(a.properties?.priority_rank) - Number(b.properties?.priority_rank));

  const filteredRows =
    filter === "All" ? allRows : allRows.filter((f) => String(f.properties?.severity ?? "") === filter);

  const visibleRows = showAll ? filteredRows : filteredRows.slice(0, ROWS_PREVIEW);

  return (
    <div
      style={{
        height: "100%",
        width: "100%",
        background: "var(--color-panel)",
        borderLeft: "1px solid var(--color-border)",
        padding: "16px",
        overflowY: "auto",
        boxSizing: "border-box",
      }}
    >
      <h2 style={{ fontSize: "var(--font-size-sm)", margin: "0 0 4px", color: "var(--color-text-secondary)" }}>
        Priority queue
      </h2>
      <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 10px" }}>
        {allRows.length} kept changes ranked by severity, confidence, and closeness to a hospital or school.
      </p>

      <div style={{ display: "flex", gap: "4px", marginBottom: "12px" }}>
        {SEVERITY_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setFilter(s);
              setShowAll(false);
            }}
            style={{
              flex: 1,
              padding: "4px 6px",
              fontSize: "var(--font-size-xs)",
              borderRadius: "var(--radius-sm)",
              border: `1px solid ${filter === s ? "var(--color-accent)" : "var(--color-border)"}`,
              background: filter === s ? "var(--color-accent)" : "white",
              color: filter === s ? "white" : "var(--color-text)",
              cursor: "pointer",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {filteredRows.length === 0 && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
          No kept changes match this filter.
        </p>
      )}

      {visibleRows.map((f) => {
        const p = f.properties as Record<string, unknown>;
        const id = String(p.id);
        const severity = String(p.severity ?? "");
        const popBuffer = p.population_buffer_est as number | null;
        const isHovered = hoveredId === id;
        return (
          <button
            key={id}
            onClick={() => onSelect(id)}
            onMouseEnter={() => onHoverRow?.(id)}
            onMouseLeave={() => onHoverRow?.(null)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "8px 10px",
              marginBottom: "6px",
              borderRadius: "var(--radius-sm)",
              border: `1px solid ${isHovered ? "var(--color-accent)" : "var(--color-border)"}`,
              background: isHovered ? "rgba(47,93,70,0.06)" : "white",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "2px",
                  background: SEVERITY_COLOR[severity] ?? "#8A8F98",
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              <span style={{ fontWeight: 600, fontSize: "var(--font-size-sm)" }}>
                #{Math.round(Number(p.priority_rank))}
              </span>
              <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
                {CHANGE_TYPE_LABEL[String(p.change_type ?? "")] ?? String(p.change_type ?? "—")}
              </span>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: "4px",
                fontSize: "var(--font-size-xs)",
              }}
            >
              <span className="mono">{Number(p.area_m2 ?? 0).toLocaleString()} m²</span>
              <span className="mono">{nearestFacilityLabel(p)}</span>
            </div>
            {popBuffer != null && popBuffer >= 1 && (
              <div style={{ marginTop: "2px", fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
                ~{Math.round(popBuffer).toLocaleString()} people estimated nearby
              </div>
            )}
            <div
              style={{
                marginTop: "4px",
                fontSize: "var(--font-size-xs)",
                color: "var(--color-text-secondary)",
                lineHeight: 1.4,
              }}
            >
              {String(p.priority_reason ?? "")}
            </div>
          </button>
        );
      })}

      {!showAll && filteredRows.length > ROWS_PREVIEW && (
        <button
          onClick={() => setShowAll(true)}
          style={{
            width: "100%",
            padding: "8px",
            fontSize: "var(--font-size-xs)",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--color-border)",
            background: "white",
            color: "var(--color-accent)",
            cursor: "pointer",
          }}
        >
          Show all ({filteredRows.length})
        </button>
      )}
    </div>
  );
}
