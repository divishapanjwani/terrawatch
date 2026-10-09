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

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        right: 0,
        bottom: 0,
        width: "320px",
        background: "var(--color-panel)",
        borderLeft: "1px solid var(--color-border)",
        padding: "16px",
        overflowY: "auto",
        zIndex: 20,
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
