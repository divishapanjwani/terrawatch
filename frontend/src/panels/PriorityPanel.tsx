import { useState } from "react";
import type { Feature, FeatureCollection } from "geojson";
import {
  Building2,
  Droplets,
  Home,
  HelpCircle,
  Hospital,
  Mountain,
  School,
  TreeDeciduous,
  Users,
} from "lucide-react";

const SEVERITY_PILL: Record<string, string> = {
  High: "ts-pill-high",
  Medium: "ts-pill-medium",
  Low: "ts-pill-low",
};

const CHANGE_TYPE_LABEL: Record<string, string> = {
  new_construction: "New construction",
  structure_lost: "Structure lost",
  flooding: "Flooding",
  landslide_bare_soil: "Landslide / bare soil",
  vegetation_loss: "Vegetation loss",
  other: "Other / unclassified",
};

const CHANGE_TYPE_ICON: Record<string, React.ComponentType<{ size?: number }>> = {
  new_construction: Building2,
  structure_lost: Home,
  flooding: Droplets,
  landslide_bare_soil: Mountain,
  vegetation_loss: TreeDeciduous,
  other: HelpCircle,
};

const SEVERITY_FILTERS = ["All", "High", "Medium", "Low"] as const;
type SeverityFilter = (typeof SEVERITY_FILTERS)[number];

const ROWS_PREVIEW = 10;

function nearestFacility(p: Record<string, unknown>): { label: string; dist: number; Icon: typeof Hospital } | null {
  const hospM = p.nearest_hospital_m as number | null;
  const schoolM = p.nearest_school_m as number | null;
  const candidates: [number, string, typeof Hospital][] = [];
  if (hospM != null) candidates.push([hospM, "Hospital", Hospital]);
  if (schoolM != null) candidates.push([schoolM, "School", School]);
  if (!candidates.length) return null;
  candidates.sort((a, b) => a[0] - b[0]);
  const [dist, label, Icon] = candidates[0];
  return { label, dist, Icon };
}

export default function PriorityPanel({
  geojson,
  onSelect,
  hoveredId,
  onHoverRow,
  selectedId,
}: {
  geojson: FeatureCollection;
  onSelect: (id: string) => void;
  hoveredId?: string | null;
  onHoverRow?: (id: string | null) => void;
  selectedId?: string | null;
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
    <div style={{ padding: "14px", display: "flex", flexDirection: "column", gap: "10px" }}>
      <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: 0, lineHeight: 1.4 }}>
        {allRows.length} kept changes ranked by severity, confidence, and closeness to a hospital or school.
      </p>

      <div className="ts-segment" style={{ width: "100%" }}>
        {SEVERITY_FILTERS.map((s) => (
          <button
            key={s}
            className={filter === s ? "active" : ""}
            style={{ flex: 1 }}
            onClick={() => {
              setFilter(s);
              setShowAll(false);
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {filteredRows.length === 0 && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-faint)" }}>No kept changes match this filter.</p>
      )}

      {visibleRows.map((f) => {
        const p = f.properties as Record<string, unknown>;
        const id = String(p.id);
        const severity = String(p.severity ?? "");
        const popBuffer = p.population_buffer_est as number | null;
        const isHovered = hoveredId === id;
        const isSelected = selectedId === id;
        const changeType = String(p.change_type ?? "");
        const ChangeIcon = CHANGE_TYPE_ICON[changeType] ?? HelpCircle;
        const facility = nearestFacility(p);

        return (
          <button
            key={id}
            onClick={() => onSelect(id)}
            onMouseEnter={() => onHoverRow?.(id)}
            onMouseLeave={() => onHoverRow?.(null)}
            className="ts-card"
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "11px 12px",
              cursor: "pointer",
              borderColor: isSelected ? "var(--color-accent)" : isHovered ? "var(--color-border-strong)" : "var(--color-border)",
              background: isSelected ? "var(--color-accent-soft)" : isHovered ? "var(--color-card-hover)" : "var(--color-card)",
              transition: "background var(--transition-fast), border-color var(--transition-fast)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "7px" }}>
              <span className="mono" style={{ fontSize: "var(--font-size-sm)", fontWeight: 700, color: "var(--color-text-secondary)", width: "26px" }}>
                #{Math.round(Number(p.priority_rank))}
              </span>
              <span className={`ts-pill ${SEVERITY_PILL[severity] ?? "ts-pill-neutral"}`}>
                <span className="ts-pill-dot" style={{ background: "currentColor" }} />
                {severity || "—"}
              </span>
              <div style={{ flex: 1 }} />
              <ChangeIcon size={13} />
            </div>

            <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text)", marginBottom: "6px" }}>
              {CHANGE_TYPE_LABEL[changeType] ?? changeType}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "var(--font-size-xs)", marginBottom: popBuffer || facility ? "6px" : 0 }}>
              <span className="mono" style={{ color: "var(--color-text-secondary)" }}>
                {Number(p.area_m2 ?? 0).toLocaleString()} m²
              </span>
              {facility && (
                <span className="mono" style={{ color: "var(--color-text-secondary)", display: "flex", alignItems: "center", gap: "4px" }}>
                  <facility.Icon size={11} />
                  {facility.label} · {facility.dist.toLocaleString(undefined, { maximumFractionDigits: 0 })} m
                </span>
              )}
            </div>

            {popBuffer != null && popBuffer >= 1 && (
              <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", marginBottom: "6px" }}>
                <Users size={11} />
                ~{Math.round(popBuffer).toLocaleString()} people estimated nearby
              </div>
            )}

            <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-faint)", lineHeight: 1.4 }}>
              {String(p.priority_reason ?? "")}
            </div>
          </button>
        );
      })}

      {!showAll && filteredRows.length > ROWS_PREVIEW && (
        <button className="ts-btn ts-btn-sm" onClick={() => setShowAll(true)} style={{ width: "100%" }}>
          Show all ({filteredRows.length})
        </button>
      )}
    </div>
  );
}
