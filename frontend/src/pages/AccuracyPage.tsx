import { useEffect, useState } from "react";
import { API_BASE } from "../api/client";

interface MetricRecord {
  engine: string;
  dataset: string;
  stage?: string;
  n_images: number;
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  accuracy: number;
  false_positive_rate: number;
  elapsed_seconds: number;
}

const ENGINE_LABEL: Record<string, string> = {
  siamese_levir_cd: "TinyCD (Engine 1)",
  unet_oscd: "U-Net (Engine 2)",
  spectral_baseline: "Spectral baseline",
};

const STAGE_LABEL: Record<string, string> = {
  raw: "Raw model",
  morphology: "+ morphology",
  false_alarm_filter: "+ false-alarm filter",
  full: "Full pipeline",
};

const STAGE_ORDER = ["raw", "morphology", "false_alarm_filter", "full"];

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function MiniAblationChart({ rows }: { rows: MetricRecord[] }) {
  const max = Math.max(...rows.map((r) => r.precision), 0.01);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: "16px", height: "80px", padding: "0 4px" }}>
      {rows.map((r) => (
        <div key={r.stage ?? "full"} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "6px", flex: 1 }}>
          <span className="mono" style={{ fontSize: "10px", color: "var(--color-text-secondary)" }}>
            {pct(r.precision)}
          </span>
          <div
            style={{
              width: "100%",
              maxWidth: "36px",
              height: `${Math.max(4, (r.precision / max) * 48)}px`,
              background: "var(--color-accent)",
              borderRadius: "3px 3px 0 0",
              opacity: 0.5 + 0.5 * (r.precision / max),
            }}
          />
          <span style={{ fontSize: "10px", color: "var(--color-text-faint)", textAlign: "center" }}>
            {STAGE_LABEL[r.stage ?? "full"]?.replace("+ ", "+") ?? r.stage}
          </span>
        </div>
      ))}
    </div>
  );
}

function MetricCard({ engine, dataset, rows }: { engine: string; dataset: string; rows: MetricRecord[] }) {
  const raw = rows[0];
  const filtered = rows[rows.length - 1];
  const hasFilterStage = rows.length > 1;
  const headline = filtered;

  return (
    <div className="ts-card ts-fade-up" style={{ padding: "14px 16px", flex: "1 1 220px", minWidth: "220px" }}>
      <div className="ts-label" style={{ marginBottom: "2px" }}>
        {ENGINE_LABEL[engine] ?? engine}
      </div>
      <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-faint)", marginBottom: "10px" }}>{dataset}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "4px" }}>
        <span className="ts-metric" style={{ fontSize: "var(--font-size-2xl)" }}>
          {headline.f1.toFixed(3)}
        </span>
        <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
          F1 {hasFilterStage ? "with filter" : ""}
        </span>
      </div>
      {hasFilterStage && (
        <div className="mono" style={{ fontSize: "10px", color: "var(--color-text-faint)", marginBottom: "10px" }}>
          raw {raw.f1.toFixed(3)} → with filter {filtered.f1.toFixed(3)}
        </div>
      )}
      {!hasFilterStage && <div style={{ marginBottom: "6px" }} />}
      <div style={{ display: "flex", gap: "14px", fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
        <span>
          P <span className="mono" style={{ color: "var(--color-text)" }}>{pct(headline.precision)}</span>
        </span>
        <span>
          R <span className="mono" style={{ color: "var(--color-text)" }}>{pct(headline.recall)}</span>
        </span>
      </div>
    </div>
  );
}

export default function AccuracyPage() {
  const [results, setResults] = useState<MetricRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/metrics`)
      .then((r) => r.json())
      .then((data) => setResults(data.results ?? []))
      .catch((e) => setError(String(e)));
  }, []);

  const groups = new Map<string, MetricRecord[]>();
  for (const r of results ?? []) {
    const key = `${r.engine}__${r.dataset}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(r);
  }
  for (const rows of groups.values()) {
    rows.sort((a, b) => STAGE_ORDER.indexOf(a.stage ?? "full") - STAGE_ORDER.indexOf(b.stage ?? "full"));
  }

  return (
    <div className="ts-scroll" style={{ padding: "32px", maxWidth: "980px", overflowY: "auto", height: "100%" }}>
      <h1 style={{ fontSize: "var(--font-size-xl)", fontWeight: 700, margin: "0 0 6px", letterSpacing: "-0.01em" }}>Accuracy</h1>
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", margin: "0 0 24px", lineHeight: 1.5, maxWidth: "720px" }}>
        Real numbers from <code className="mono">scripts/evaluate.py</code>, run against each engine's held-out test
        split (TinyCD on LEVIR-CD, Engine 2 and the spectral baseline on OSCD). <code className="mono">--ablation</code>{" "}
        breaks each engine down into raw model → + morphology → + false-alarm filter, so you can see what each stage
        actually buys you. Never estimated or made up — re-run the script to refresh this table.
      </p>

      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-xs)" }}>{error}</p>}
      {results === null && !error && <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>Loading…</p>}
      {results && results.length === 0 && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
          No evaluation results yet. Run <code className="mono">python scripts/evaluate.py levircd --ablation</code> or{" "}
          <code className="mono">python scripts/evaluate.py oscd --engine engine2 --ablation</code> from{" "}
          <code className="mono">backend/</code>.
        </p>
      )}

      {groups.size > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", marginBottom: "28px" }}>
          {Array.from(groups.entries()).map(([key, rows]) => {
            const [engine, dataset] = key.split("__");
            return <MetricCard key={key} engine={engine} dataset={dataset} rows={rows} />;
          })}
        </div>
      )}

      {Array.from(groups.entries()).map(([key, rows]) => {
        const [engine, dataset] = key.split("__");
        return (
          <div key={key} className="ts-card" style={{ marginBottom: "20px", padding: "16px 18px" }}>
            <h2 style={{ fontSize: "var(--font-size-sm)", fontWeight: 600, margin: "0 0 2px" }}>{ENGINE_LABEL[engine] ?? engine}</h2>
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-faint)", margin: "0 0 12px" }}>{dataset}</p>

            {rows.length > 1 && <MiniAblationChart rows={rows} />}

            <div style={{ overflowX: "auto", marginTop: "12px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--font-size-sm)" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                    {["Stage", "N", "Precision", "Recall", "F1", "Accuracy", "FPR", "Threshold"].map((h) => (
                      <th key={h} className="ts-label" style={{ textAlign: "left", padding: "6px 10px", fontWeight: 600 }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.stage ?? "full"} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ padding: "8px 10px", color: "var(--color-text)" }}>{STAGE_LABEL[r.stage ?? "full"] ?? r.stage}</td>
                      <td className="mono" style={{ padding: "8px 10px", color: "var(--color-text-secondary)" }}>
                        {r.n_images}
                      </td>
                      <td className="mono" style={{ padding: "8px 10px", color: "var(--color-text-secondary)" }}>
                        {pct(r.precision)}
                      </td>
                      <td className="mono" style={{ padding: "8px 10px", color: "var(--color-text-secondary)" }}>
                        {pct(r.recall)}
                      </td>
                      <td className="mono" style={{ padding: "8px 10px", fontWeight: 600, color: "var(--color-accent)" }}>
                        {r.f1.toFixed(3)}
                      </td>
                      <td className="mono" style={{ padding: "8px 10px", color: "var(--color-text-secondary)" }}>
                        {pct(r.accuracy)}
                      </td>
                      <td className="mono" style={{ padding: "8px 10px", color: "var(--color-text-secondary)" }}>
                        {pct(r.false_positive_rate)}
                      </td>
                      <td className="mono" style={{ padding: "8px 10px", color: "var(--color-text-faint)" }}>
                        {r.threshold}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      {results && results.length > 0 && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-faint)", marginTop: "8px", lineHeight: 1.5 }}>
          TinyCD is trained on 0.5m LEVIR-CD aerial photos and evaluated on that dataset's own 128-image test split.
          Engine 2 and the spectral baseline are evaluated on OSCD's 10-city Sentinel-2 test split — a much smaller,
          much harder (10m/pixel) benchmark, which is reflected in the lower numbers. These are two different tasks,
          not a head-to-head comparison, except where the spectral baseline and Engine 2 share the same OSCD rows.
        </p>
      )}
    </div>
  );
}
