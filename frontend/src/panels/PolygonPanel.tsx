import type { ReactNode } from "react";
import type { MapGeoJSONFeature } from "maplibre-gl";
import {
  AlertTriangle,
  Building2,
  Droplets,
  ExternalLink,
  HelpCircle,
  Home,
  Hospital,
  Mountain,
  Route,
  School,
  TreeDeciduous,
  X,
} from "lucide-react";

const SEVERITY_PILL: Record<string, string> = {
  High: "ts-pill-high",
  Medium: "ts-pill-medium",
  Low: "ts-pill-low",
};

// Mirrors app/pipeline/false_alarm.py REASON_LABELS -- plain-language
// explanation shown when a rejected polygon is clicked.
const REJECT_REASON_LABELS: Record<string, string> = {
  cloud: "Overlaps a cloud in the before or after image.",
  too_small: "Smaller than the minimum area for a real change.",
  misalignment_edge: "Sits at the edge of the valid image area, likely an alignment artifact.",
  vegetation_seasonal:
    "Looks like a seasonal vegetation change (color shift only, no sign of construction, water, or bare soil).",
  shadow_illumination:
    "Brightness changed but the underlying structure/texture didn't — likely a shadow or lighting change.",
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

const FACILITY_ICON: Record<string, React.ComponentType<{ size?: number }>> = {
  hospital: Hospital,
  school: School,
  shelter: Home,
  road: Route,
};

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        padding: "6px 0",
        borderBottom: "1px solid var(--color-border)",
        fontSize: "var(--font-size-xs)",
        gap: "12px",
      }}
    >
      <span style={{ color: "var(--color-text-secondary)", flexShrink: 0 }}>{label}</span>
      <span className="mono" style={{ color: "var(--color-text)", textAlign: "right" }}>
        {value}
      </span>
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
  const ChangeIcon = CHANGE_TYPE_ICON[changeType] ?? HelpCircle;
  let nearbyFacilities: { type: string; name: string; distance_m: number }[] = [];
  try {
    nearbyFacilities = p.nearby_facilities_json ? JSON.parse(String(p.nearby_facilities_json)) : [];
  } catch {
    nearbyFacilities = [];
  }

  const whyText = isRejected
    ? (REJECT_REASON_LABELS[rejectReason] ?? `${rejectReason || "No reason recorded"}.`)
    : p.change_type_rule
      ? String(p.change_type_rule)
      : null;

  return (
    <div style={{ padding: "14px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {isRejected ? (
            <span className="ts-pill ts-pill-rejected">Rejected</span>
          ) : (
            <span className={`ts-pill ${SEVERITY_PILL[severity] ?? "ts-pill-neutral"}`}>
              <span className="ts-pill-dot" style={{ background: "currentColor" }} />
              {severity || "—"}
            </span>
          )}
          {!isRejected && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: "5px",
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text)",
              }}
            >
              <ChangeIcon size={14} />
              {CHANGE_TYPE_LABEL[changeType] ?? (changeType || "—")}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="ts-btn-ghost"
          style={{
            border: "none",
            background: "none",
            cursor: "pointer",
            padding: "2px",
            color: "var(--color-text-secondary)",
          }}
          aria-label="Close"
        >
          <X size={16} />
        </button>
      </div>

      {!isRejected && Boolean(p.in_hazard_zone) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            margin: "0 0 12px",
            padding: "9px 11px",
            background: "var(--color-danger-soft)",
            border: "1px solid rgba(229,72,77,0.35)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-severity-high)",
            fontWeight: 600,
          }}
        >
          <AlertTriangle size={14} style={{ flexShrink: 0 }} />
          New structure detected in hazard zone — verify
        </div>
      )}

      {needsReview && !isRejected && (
        <div
          style={{
            margin: "0 0 12px",
            padding: "7px 11px",
            background: "var(--color-warning-soft)",
            border: "1px dotted rgba(245,165,36,0.5)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-warning)",
          }}
        >
          Needs human review — confidence below threshold.
        </div>
      )}

      {whyText && (
        <div className="ts-card" style={{ padding: "10px 12px", marginBottom: "12px" }}>
          <div className="ts-label" style={{ marginBottom: "5px" }}>
            Why {isRejected ? "rejected" : "this type"}
          </div>
          <p
            style={{
              margin: 0,
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-secondary)",
              lineHeight: 1.5,
            }}
          >
            {whyText}
          </p>
        </div>
      )}

      <Row label="ID" value={String(p.id ?? "—")} />
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
            p.nearest_hospital_m != null ? `${Number(p.nearest_hospital_m).toLocaleString()} m` : "none found"
          }
        />
      )}
      {!isRejected && (
        <Row
          label="Nearest school"
          value={
            p.nearest_school_m != null ? `${Number(p.nearest_school_m).toLocaleString()} m` : "none found"
          }
        />
      )}
      {!isRejected && (
        <Row
          label="Nearest main road"
          value={
            p.nearest_main_road_m != null
              ? `${Number(p.nearest_main_road_m).toLocaleString()} m`
              : "none found"
          }
        />
      )}
      {!isRejected && (
        <Row
          label="Population (inside)"
          value={
            p.population_est != null ? `~${Math.round(Number(p.population_est)).toLocaleString()}` : "no data"
          }
        />
      )}
      {!isRejected && (
        <Row
          label="Population (+buffer)"
          value={
            p.population_buffer_est != null
              ? `~${Math.round(Number(p.population_buffer_est)).toLocaleString()}`
              : "no data"
          }
        />
      )}

      {!isRejected && nearbyFacilities.length > 0 && (
        <div style={{ marginTop: "14px" }}>
          <div className="ts-label" style={{ marginBottom: "6px" }}>
            Nearby facilities
          </div>
          {nearbyFacilities.map((f, i) => {
            const Icon = FACILITY_ICON[f.type] ?? Hospital;
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "5px 0",
                  fontSize: "var(--font-size-xs)",
                }}
              >
                <Icon size={13} />
                <span
                  style={{
                    color: "var(--color-text)",
                    flex: 1,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {f.name}
                </span>
                <span className="mono" style={{ color: "var(--color-text-secondary)", flexShrink: 0 }}>
                  {f.distance_m.toFixed(0)} m
                </span>
              </div>
            );
          })}
        </div>
      )}

      {!isRejected && p.priority_reason ? (
        <p
          style={{
            marginTop: "14px",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-text-secondary)",
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: "var(--color-text)" }}>Priority reason:</strong> {String(p.priority_reason)}
        </p>
      ) : null}

      <a
        href={gmapsUrl}
        target="_blank"
        rel="noreferrer"
        className="ts-btn"
        style={{ width: "100%", marginTop: "16px", textDecoration: "none" }}
      >
        Open in Google Maps
        <ExternalLink size={13} />
      </a>

      <p
        style={{
          marginTop: "16px",
          fontSize: "var(--font-size-xs)",
          color: "var(--color-text-faint)",
          lineHeight: 1.5,
        }}
      >
        {isRejected
          ? "Rejected changes are excluded from severity scoring and the priority queue, but kept here for transparency."
          : "Severity measures change strength, not confirmed damage. sev_score = max(norm(log area_m²), norm(log change_magnitude)) — log-scaled so one huge outlier doesn't flatten the rest, and a change counts as severe if it's very large OR very intense; High ≥ 0.66, Medium ≥ 0.33, else Low."}
      </p>
    </div>
  );
}
