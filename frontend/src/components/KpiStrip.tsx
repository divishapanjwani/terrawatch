import type { FeatureCollection } from "geojson";
import { AlertTriangle, CheckCircle2, MapPinned, Ruler, Users } from "lucide-react";
import { useMemo } from "react";
import type { AnalysisStatus } from "../api/client";
import { useCountUp } from "../hooks/useCountUp";

const SEVERITY_COLOR: Record<string, string> = {
  High: "var(--color-severity-high)",
  Medium: "var(--color-severity-medium)",
  Low: "var(--color-severity-low)",
};

function Card({
  icon,
  label,
  value,
  suffix,
  prefix,
  decimals = 0,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  children?: React.ReactNode;
}) {
  const animated = useCountUp(value);
  const display =
    (prefix ?? "") +
    animated.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return (
    <div
      className="ts-card ts-fade-up"
      style={{
        flex: 1,
        minWidth: 0,
        padding: "14px 16px",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
    >
      <div
        style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--color-text-secondary)" }}
      >
        {icon}
        <span className="ts-label">{label}</span>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "4px" }}>
        <span className="ts-metric" style={{ fontSize: "var(--font-size-2xl)" }}>
          {display}
        </span>
        {suffix && (
          <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
            {suffix}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function MiniStackedBar({ segments }: { segments: { color: string; count: number; label: string }[] }) {
  const total = segments.reduce((s, seg) => s + seg.count, 0);
  if (total === 0) return null;
  return (
    <div>
      <div style={{ display: "flex", height: "4px", borderRadius: "2px", overflow: "hidden", gap: "1px" }}>
        {segments.map((seg) =>
          seg.count > 0 ? (
            <div
              key={seg.label}
              style={{ flex: seg.count, background: seg.color }}
              title={`${seg.label}: ${seg.count}`}
            />
          ) : null,
        )}
      </div>
      <div style={{ display: "flex", gap: "8px", marginTop: "5px", flexWrap: "wrap" }}>
        {segments.map((seg) => (
          <span key={seg.label} style={{ fontSize: "10px", color: "var(--color-text-secondary)" }}>
            <span style={{ color: seg.color, fontWeight: 600 }}>{seg.count}</span> {seg.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function KpiStrip({
  analysis,
  geojson,
}: {
  analysis: AnalysisStatus;
  geojson: FeatureCollection;
}) {
  const stats = useMemo(() => {
    let areaM2 = 0;
    const severityCounts: Record<string, number> = { High: 0, Medium: 0, Low: 0 };
    for (const f of geojson.features) {
      const p = f.properties;
      if (p?.status !== "kept") continue;
      areaM2 += Number(p.area_m2 ?? 0);
      const sev = String(p.severity ?? "");
      if (sev in severityCounts) severityCounts[sev] += 1;
    }
    return { areaKm2: areaM2 / 1_000_000, severityCounts };
  }, [geojson]);

  const rejectEntries = Object.entries(analysis.reject_reason_counts ?? {}).sort((a, b) => b[1] - a[1]);
  const maxReject = Math.max(1, ...rejectEntries.map(([, c]) => c));

  return (
    <div style={{ display: "flex", gap: "10px", padding: "12px 16px", flexShrink: 0 }}>
      <Card icon={<CheckCircle2 size={14} />} label="Changes kept" value={analysis.kept_count}>
        <MiniStackedBar
          segments={[
            { color: SEVERITY_COLOR.High, count: stats.severityCounts.High, label: "High" },
            { color: SEVERITY_COLOR.Medium, count: stats.severityCounts.Medium, label: "Med" },
            { color: SEVERITY_COLOR.Low, count: stats.severityCounts.Low, label: "Low" },
          ]}
        />
      </Card>

      <Card icon={<AlertTriangle size={14} />} label="False alarms rejected" value={analysis.rejected_count}>
        <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
          {rejectEntries.slice(0, 3).map(([reason, count]) => (
            <div key={reason} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div
                style={{
                  width: "40px",
                  height: "3px",
                  borderRadius: "2px",
                  background: "var(--color-border)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${(count / maxReject) * 100}%`,
                    height: "100%",
                    background: "var(--color-rejected)",
                  }}
                />
              </div>
              <span style={{ fontSize: "10px", color: "var(--color-text-secondary)" }}>
                {reason} <span className="mono">{count}</span>
              </span>
            </div>
          ))}
        </div>
      </Card>

      <Card icon={<Ruler size={14} />} label="Area changed" value={stats.areaKm2} suffix="km²" decimals={1} />

      <Card
        icon={<Users size={14} />}
        label="People in changed areas"
        value={
          analysis.population_available && analysis.total_population_buffer_est != null
            ? analysis.total_population_buffer_est
            : 0
        }
        prefix={analysis.population_available ? "~" : undefined}
        suffix={analysis.population_available ? "(estimate)" : "no data"}
        decimals={0}
      />

      <Card
        icon={<MapPinned size={14} />}
        label="Priority areas near facility"
        value={analysis.near_facility_count ?? 0}
        decimals={0}
      />
    </div>
  );
}
