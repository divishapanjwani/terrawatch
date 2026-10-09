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

function nearestFacilityLabel(p: Record<string, unknown>): string {
  const hospM = p.nearest_hospital_m as number | null;
  const schoolM = p.nearest_school_m as number | null;
  const candidates: [number, string][] = [];
  if (hospM != null) candidates.push([hospM, "hospital"]);
  if (schoolM != null) candidates.push([schoolM, "school"]);
  if (!candidates.length) return "—";
  candidates.sort((a, b) => a[0] - b[0]);
  const [dist, label] = candidates[0];
  return `${dist.toLocaleString(undefined, { maximumFractionDigits: 0 })} m (${label})`;
}

export default function PriorityPanel({
  geojson,
  onSelect,
}: {
  geojson: FeatureCollection;
  onSelect: (id: string) => void;
}) {
  const rows = (geojson.features as Feature[])
    .filter((f) => f.properties?.status === "kept" && f.properties?.priority_rank != null)
    .sort((a, b) => Number(a.properties?.priority_rank) - Number(b.properties?.priority_rank));

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        bottom: 0,
        width: "360px",
        background: "var(--color-panel)",
        borderLeft: "1px solid var(--color-border)",
        padding: "16px",
        overflowY: "auto",
        zIndex: 20,
      }}
    >
      <h2 style={{ fontSize: "var(--font-size-sm)", margin: "0 0 4px", color: "var(--color-text-secondary)" }}>
        Priority queue
      </h2>
      <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 12px" }}>
        Kept changes ranked by severity, confidence, and closeness to a
        hospital or school. Click a row to zoom and see details.
      </p>

      {rows.length === 0 && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
          No kept changes to rank.
        </p>
      )}

      {rows.map((f) => {
        const p = f.properties as Record<string, unknown>;
        const id = String(p.id);
        const severity = String(p.severity ?? "");
        return (
          <button
            key={id}
            onClick={() => onSelect(id)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              padding: "8px 10px",
              marginBottom: "6px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--color-border)",
              background: "white",
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
    </div>
  );
}
