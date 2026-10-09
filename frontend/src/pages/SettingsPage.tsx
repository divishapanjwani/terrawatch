import { useEffect, useState } from "react";
import { getPriorityWeights, setPriorityWeights } from "../api/client";
import type { PriorityWeights } from "../api/client";

const WEIGHT_LABELS: { key: keyof PriorityWeights; label: string; hint: string }[] = [
  { key: "w1_severity", label: "w1 — Severity", hint: "change strength (area + magnitude)" },
  { key: "w2_population", label: "w2 — Population", hint: "estimated people nearby" },
  { key: "w3_facility_proximity", label: "w3 — Facility proximity", hint: "closeness to a hospital or school" },
  { key: "w4_confidence", label: "w4 — Confidence", hint: "model confidence in the detection" },
  { key: "w5_route_impact", label: "w5 — Route impact", hint: "reserved for Phase 7 (routes), currently 0" },
];

export default function SettingsPage() {
  const [weights, setWeights] = useState<PriorityWeights | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    getPriorityWeights().then(setWeights).catch(() => setStatus("Failed to load settings."));
  }, []);

  async function handleSave() {
    if (!weights) return;
    setStatus("Saving…");
    try {
      const saved = await setPriorityWeights(weights);
      setWeights(saved);
      setStatus("Saved — applies to the next analysis you run.");
    } catch (err) {
      setStatus(`Failed to save: ${(err as Error).message}`);
    }
  }

  return (
    <div style={{ flex: 1, padding: "32px", maxWidth: "560px", overflowY: "auto" }}>
      <h1 style={{ fontSize: "var(--font-size-lg)", margin: "0 0 4px" }}>Settings</h1>
      <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 24px" }}>
        Priority score weights: priority = w1·sev_score + w2·norm(population_est) + w3·facility_proximity +
        w4·confidence + w5·route_impact. Changes apply to the next analysis you run — they don't recompute
        whatever is currently on screen.
      </p>

      {!weights ? (
        <p style={{ fontSize: "var(--font-size-xs)" }}>Loading…</p>
      ) : (
        <>
          {WEIGHT_LABELS.map(({ key, label, hint }) => (
            <div key={key} style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "var(--font-size-sm)", marginBottom: "2px" }}>
                {label}
              </label>
              <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 6px" }}>
                {hint}
              </p>
              <input
                type="number"
                step="0.05"
                min="0"
                value={weights[key]}
                onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
                style={{
                  width: "120px",
                  padding: "6px 8px",
                  fontSize: "var(--font-size-sm)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-border)",
                }}
                className="mono"
              />
            </div>
          ))}

          <button
            onClick={handleSave}
            style={{
              padding: "8px 16px",
              fontSize: "var(--font-size-sm)",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--color-accent)",
              color: "white",
              cursor: "pointer",
            }}
          >
            Save
          </button>
          {status && (
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", marginTop: "10px" }}>
              {status}
            </p>
          )}
        </>
      )}
    </div>
  );
}
