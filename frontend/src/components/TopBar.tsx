import { useState } from "react";
import { Download, FileText, Satellite, Settings as SettingsIcon } from "lucide-react";
import type { AnalysisStatus, EngineChoice, ReportLang } from "../api/client";
import { exportUrl, reportUrl } from "../api/client";

const REPORT_LANGS: { value: ReportLang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिंदी" },
  { value: "mr", label: "मराठी" },
];

const ENGINE_NAME_LABEL: Record<string, string> = {
  siamese_levir_cd: "TinyCD",
  unet_oscd: "Engine 2 (U-Net)",
  spectral_baseline: "Spectral baseline",
};

export default function TopBar({
  analysisName,
  analysis,
  mode,
  onModeChange,
  onOpenSettings,
}: {
  analysisName: string | null;
  analysis: AnalysisStatus | null;
  mode: "disaster" | "prevention";
  onModeChange: (m: "disaster" | "prevention") => void;
  onOpenSettings: () => void;
}) {
  const [exportOpen, setExportOpen] = useState(false);
  const [reportLang, setReportLang] = useState<ReportLang>("en");

  return (
    <header
      style={{
        height: "56px",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        gap: "20px",
        padding: "0 16px",
        background: "var(--color-panel)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "8px",
            background: "var(--color-accent-soft)",
            border: "1px solid var(--color-accent-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Satellite size={15} color="var(--color-accent)" strokeWidth={2} />
        </div>
        <span style={{ fontSize: "var(--font-size-base)", fontWeight: 600, letterSpacing: "-0.01em" }}>
          TerraWatch <span style={{ color: "var(--color-accent)" }}>AI</span>
        </span>
      </div>

      {analysisName && (
        <>
          <div style={{ width: "1px", height: "20px", background: "var(--color-border)" }} />
          <span
            className="mono"
            style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}
          >
            {analysisName}
          </span>
        </>
      )}

      {analysis?.engine && (
        <span className="ts-pill ts-pill-neutral">
          {ENGINE_NAME_LABEL[analysis.engine] ?? analysis.engine}
        </span>
      )}

      <div style={{ flex: 1 }} />

      <div className="ts-segment">
        {(["disaster", "prevention"] as const).map((m) => (
          <button key={m} className={mode === m ? "active" : ""} onClick={() => onModeChange(m)}>
            {m === "disaster" ? "Disaster" : "Prevention"}
          </button>
        ))}
      </div>

      {analysis && (
        <div style={{ position: "relative" }}>
          <button className="ts-btn ts-btn-sm" onClick={() => setExportOpen((o) => !o)}>
            <Download size={14} />
            Export
          </button>
          {exportOpen && (
            <div
              className="ts-card ts-fade-up"
              style={{
                position: "absolute",
                top: "calc(100% + 6px)",
                right: 0,
                minWidth: "160px",
                padding: "6px",
                zIndex: 50,
              }}
              onMouseLeave={() => setExportOpen(false)}
            >
              {(["geojson", "gpkg"] as const).map((fmt) => (
                <a
                  key={fmt}
                  href={exportUrl(analysis.id, fmt)}
                  onClick={() => setExportOpen(false)}
                  style={{
                    display: "block",
                    padding: "8px 10px",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text)",
                    textDecoration: "none",
                    borderRadius: "4px",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-card-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  {fmt === "geojson" ? "Export GeoJSON" : "Export GeoPackage"}
                </a>
              ))}

              <div
                style={{
                  margin: "6px -6px",
                  borderTop: "1px solid var(--color-border)",
                  padding: "8px 10px 4px",
                }}
              >
                <div
                  style={{
                    fontSize: "10px",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "var(--color-text-faint)",
                    marginBottom: "6px",
                  }}
                >
                  Field report
                </div>
                <select
                  className="ts-select"
                  value={reportLang}
                  onChange={(e) => setReportLang(e.target.value as ReportLang)}
                  style={{ width: "100%", marginBottom: "6px", fontSize: "12px" }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {REPORT_LANGS.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </select>
                <a
                  href={reportUrl(analysis.id, "pdf", reportLang)}
                  onClick={() => setExportOpen(false)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "8px 10px",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text)",
                    textDecoration: "none",
                    borderRadius: "4px",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-card-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <FileText size={13} /> Download PDF
                </a>
                <a
                  href={reportUrl(analysis.id, "html", reportLang)}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => setExportOpen(false)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "8px 10px",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text)",
                    textDecoration: "none",
                    borderRadius: "4px",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-card-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <FileText size={13} /> Open mobile report
                </a>
              </div>
            </div>
          )}
        </div>
      )}

      <button
        className="ts-btn ts-btn-ghost ts-btn-sm"
        onClick={onOpenSettings}
        title="Settings"
        aria-label="Settings"
      >
        <SettingsIcon size={16} />
      </button>
    </header>
  );
}

export function engineChoiceLabel(choice: EngineChoice): string {
  return { auto: "Auto", tinycd: "TinyCD", engine2: "Engine 2", spectral: "Spectral baseline" }[choice];
}
