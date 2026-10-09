import { useEffect, useState } from "react";
import { API_BASE } from "../api/client";

interface MetricRecord {
  engine: string;
  dataset: string;
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

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
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

  return (
    <div style={{ padding: "32px", maxWidth: "900px", overflowY: "auto", height: "100%" }}>
      <h1 style={{ fontSize: "var(--font-size-xl)", margin: "0 0 4px" }}>Accuracy</h1>
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", margin: "0 0 24px" }}>
        Real numbers from <code className="mono">scripts/evaluate.py</code>, run against each
        engine's held-out test split (TinyCD on LEVIR-CD, Engine 2 and the spectral baseline on
        OSCD). Never estimated or made up — re-run the script to refresh this table.
      </p>

      {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-xs)" }}>{error}</p>}
      {results === null && !error && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>Loading…</p>
      )}
      {results && results.length === 0 && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
          No evaluation results yet. Run <code className="mono">python scripts/evaluate.py levircd</code>{" "}
          or <code className="mono">python scripts/evaluate.py oscd --engine engine2</code> from{" "}
          <code className="mono">backend/</code>.
        </p>
      )}

      {results && results.length > 0 && (
        <div style={{ overflowX: "auto", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--font-size-sm)" }}>
            <thead>
              <tr style={{ background: "var(--color-bg)", borderBottom: "1px solid var(--color-border)" }}>
                {["Engine", "Dataset", "N", "Precision", "Recall", "F1", "Accuracy", "FPR", "Threshold"].map(
                  (h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: "left",
                        padding: "8px 12px",
                        fontWeight: 600,
                        color: "var(--color-text-secondary)",
                        fontSize: "var(--font-size-xs)",
                      }}
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={`${r.engine}-${r.dataset}`} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  <td style={{ padding: "8px 12px" }}>{ENGINE_LABEL[r.engine] ?? r.engine}</td>
                  <td style={{ padding: "8px 12px", color: "var(--color-text-secondary)" }}>{r.dataset}</td>
                  <td className="mono" style={{ padding: "8px 12px" }}>
                    {r.n_images}
                  </td>
                  <td className="mono" style={{ padding: "8px 12px" }}>
                    {pct(r.precision)}
                  </td>
                  <td className="mono" style={{ padding: "8px 12px" }}>
                    {pct(r.recall)}
                  </td>
                  <td className="mono" style={{ padding: "8px 12px", fontWeight: 600 }}>
                    {r.f1.toFixed(3)}
                  </td>
                  <td className="mono" style={{ padding: "8px 12px" }}>
                    {pct(r.accuracy)}
                  </td>
                  <td className="mono" style={{ padding: "8px 12px" }}>
                    {pct(r.false_positive_rate)}
                  </td>
                  <td className="mono" style={{ padding: "8px 12px", color: "var(--color-text-secondary)" }}>
                    {r.threshold}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", marginTop: "20px", lineHeight: 1.5 }}>
        TinyCD is trained on 0.5m LEVIR-CD aerial photos and evaluated on that dataset's own
        128-image test split. Engine 2 and the spectral baseline are evaluated on OSCD's 10-city
        Sentinel-2 test split — a much smaller, much harder (10m/pixel) benchmark, which is reflected
        in the lower numbers. These are two different tasks, not a head-to-head comparison, except
        where the spectral baseline and Engine 2 share the same OSCD rows.
      </p>
    </div>
  );
}
