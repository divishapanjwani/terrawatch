import type { ReactNode } from "react";
import type { MapGeoJSONFeature } from "maplibre-gl";

const SEVERITY_COLOR: Record<string, string> = {
  High: "#C0392B",
  Medium: "#E67E22",
  Low: "#F1C40F",
};

// Mirrors app/pipeline/false_alarm.py REASON_LABELS -- plain-language
// explanation shown when a rejected polygon is clicked.
const REJECT_REASON_LABELS: Record<string, string> = {
  cloud: "Rejected: overlaps a cloud in the before or after image.",
  too_small: "Rejected: smaller than the minimum area for a real change.",
  misalignment_edge: "Rejected: sits at the edge of the valid image area, likely an alignment artifact.",
  vegetation_seasonal:
    "Rejected: looks like a seasonal vegetation change (color shift only, no sign of construction, water, or bare soil).",
  shadow_illumination:
    "Rejected: brightness changed but the underlying structure/texture didn't — likely a shadow or lighting change.",
};

const CHANGE_TYPE_LABEL: Record<string, string> = {
  new_construction: "New construction",
  structure_lost: "Structure lost",
  flooding: "Flooding",
  landslide_bare_soil: "Landslide / bare soil",
  vegetation_loss: "Vegetation loss",
  other: "Other / unclassified",
};

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "4px 0",
        borderBottom: "1px solid var(--color-border)",
        fontSize: "var(--font-size-xs)",
      }}
    >
      <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
      <span className="mono">{value}</span>
    </div>
  );
}

export default function PolygonPanel({
  feature,
  onClose,
}: {
  feature: MapGeoJSONFeature | null;
  onClose: () => void;
}) {
  if (!feature) return null;
  const p = feature.properties as Record<string, unknown>;
  const status = String(p.status ?? "kept");
  const isRejected = status === "rejected";
  const needsReview = Boolean(p.needs_review);
  const severity = String(p.severity ?? "");
  const lat = Number(p.centroid_lat);
  const lon = Number(p.centroid_lon);
  const gmapsUrl = `https://www.google.com/maps?q=${lat},${lon}`;
  const rejectReason = String(p.reject_reason ?? "");
  const changeType = String(p.change_type ?? "");
  let nearbyFacilities: { type: string; name: string; distance_m: number }[] = [];
  try {
    nearbyFacilities = p.nearby_facilities_json ? JSON.parse(String(p.nearby_facilities_json)) : [];
  } catch {
    nearbyFacilities = [];
  }

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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <h2 style={{ fontSize: "var(--font-size-sm)", margin: "0 0 4px", color: "var(--color-text-secondary)" }}>
          Change details
        </h2>
        <button
          onClick={onClose}
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            fontSize: "var(--font-size-base)",
            color: "var(--color-text-secondary)",
            lineHeight: 1,
          }}
          aria-label="Close"
        >
          &times;
        </button>
      </div>

      {isRejected ? (
        <div
          style={{
            margin: "8px 0 16px",
            padding: "10px 12px",
            background: "rgba(138,143,152,0.12)",
            border: "1px dashed var(--color-rejected)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-xs)",
            lineHeight: 1.5,
          }}
        >
          {REJECT_REASON_LABELS[rejectReason] ?? `Rejected: ${rejectReason || "no reason recorded"}.`}
        </div>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "8px 0 16px" }}>
          <span
            style={{
              width: "12px",
              height: "12px",
              borderRadius: "2px",
              background: SEVERITY_COLOR[severity] ?? "#8A8F98",
              display: "inline-block",
            }}
          />
          <span style={{ fontSize: "var(--font-size-lg)", fontWeight: 600 }}>{severity || "—"}</span>
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>severity</span>
        </div>
      )}

      {!isRejected && Boolean(p.in_hazard_zone) && (
        <div
          style={{
            margin: "0 0 12px",
            padding: "8px 10px",
            background: "rgba(192,57,43,0.08)",
            border: "1px solid var(--color-danger)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-danger)",
            fontWeight: 600,
          }}
        >
          New structure detected in hazard zone — verify
        </div>
      )}

      {needsReview && !isRejected && (
        <div
          style={{
            margin: "0 0 12px",
            padding: "6px 10px",
            background: "rgba(184,134,11,0.1)",
            border: "1px dotted var(--color-warning)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-warning)",
          }}
        >
          Needs human review — confidence below threshold.
        </div>
      )}

      <Row label="ID" value={String(p.id ?? "—")} />
      <Row label="Status" value={status} />
      {isRejected ? (
        <Row label="Reason" value={rejectReason || "—"} />
      ) : (
        <Row label="Change type (estimated)" value={CHANGE_TYPE_LABEL[changeType] ?? (changeType || "—")} />
      )}
      <Row label="Area" value={`${Number(p.area_m2 ?? 0).toLocaleString()} m²`} />
      <Row label="Change magnitude" value={Number(p.change_magnitude ?? 0).toFixed(2)} />
      <Row label="Confidence" value={`${(Number(p.confidence ?? 0) * 100).toFixed(0)}%`} />
      {!isRejected && <Row label="Severity score" value={Number(p.sev_score ?? 0).toFixed(2)} />}
      <Row label="Engine" value={String(p.engine ?? "—")} />
      <Row label="Centroid" value={`${lat.toFixed(5)}, ${lon.toFixed(5)}`} />
      {!isRejected && p.priority_rank != null && (
        <>
          <Row label="Priority rank" value={`#${Math.round(Number(p.priority_rank))}`} />
          <Row label="Priority score" value={Number(p.priority_score ?? 0).toFixed(2)} />
        </>
      )}
      {!isRejected && (
        <Row
          label="Nearest hospital"
          value={
            p.nearest_hospital_m != null
              ? `${Number(p.nearest_hospital_m).toLocaleString()} m — ${String(p.nearest_hospital_name ?? "")}`
              : "none found"
          }
        />
      )}
      {!isRejected && (
        <Row
          label="Nearest school"
          value={
            p.nearest_school_m != null
              ? `${Number(p.nearest_school_m).toLocaleString()} m — ${String(p.nearest_school_name ?? "")}`
              : "none found"
          }
        />
      )}
      {!isRejected && (
        <Row
          label="Nearest main road"
          value={p.nearest_main_road_m != null ? `${Number(p.nearest_main_road_m).toLocaleString()} m` : "none found"}
        />
      )}
      {!isRejected && (
        <Row
          label="Population (inside)"
          value={p.population_est != null ? `~${Math.round(Number(p.population_est)).toLocaleString()} (estimate)` : "no data"}
        />
      )}
      {!isRejected && (
        <Row
          label="Population (+buffer)"
          value={
            p.population_buffer_est != null
              ? `~${Math.round(Number(p.population_buffer_est)).toLocaleString()} (estimate)`
              : "no data"
          }
        />
      )}

      {!isRejected && nearbyFacilities.length > 0 && (
        <div style={{ marginTop: "12px" }}>
          <h3 style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 6px" }}>
            Nearby facilities
          </h3>
          {nearbyFacilities.map((f, i) => (
            <Row key={i} label={`${f.type[0].toUpperCase()}${f.type.slice(1)}`} value={`${f.name} — ${f.distance_m.toFixed(0)} m`} />
          ))}
        </div>
      )}

      <a
        href={gmapsUrl}
        target="_blank"
        rel="noreferrer"
        style={{
          display: "block",
          marginTop: "16px",
          textAlign: "center",
          padding: "8px",
          fontSize: "var(--font-size-xs)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          color: "var(--color-accent)",
          textDecoration: "none",
        }}
      >
        Open in Google Maps
      </a>

      {!isRejected && p.priority_reason ? (
        <p style={{ marginTop: "16px", fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
          <strong>Priority reason:</strong> {String(p.priority_reason)}
        </p>
      ) : null}

      {!isRejected && changeType && p.change_type_rule ? (
        <p style={{ marginTop: "16px", fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", lineHeight: 1.5 }}>
          <strong>Why this type:</strong> {String(p.change_type_rule)}
        </p>
      ) : null}

      <p
        style={{
          marginTop: "16px",
          fontSize: "var(--font-size-xs)",
          color: "var(--color-text-secondary)",
          lineHeight: 1.5,
        }}
      >
        {isRejected
          ? "Rejected changes are excluded from severity scoring and the priority queue, but kept here for transparency."
          : "Severity measures change strength, not confirmed damage. sev_score = 0.5·norm(area_m²) + 0.5·norm(change_magnitude); High ≥ 0.66, Medium ≥ 0.33, else Low."}
      </p>
    </div>
  );
}
