import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { getPriorityWeights, setPriorityWeights } from "../api/client";
import type { PriorityWeights } from "../api/client";

const WEIGHT_LABELS: { key: keyof PriorityWeights; label: string; hint: string }[] = [
  { key: "w1_severity", label: "w1 — Severity", hint: "change strength (area + magnitude)" },
  { key: "w2_population", label: "w2 — Population", hint: "estimated people nearby" },
  { key: "w3_facility_proximity", label: "w3 — Facility proximity", hint: "closeness to a hospital or school" },
  { key: "w4_confidence", label: "w4 — Confidence", hint: "model confidence in the detection" },
  { key: "w5_route_impact", label: "w5 — Route impact", hint: "reserved for Phase 7 (routes), currently 0" },
];

// Mirrors app/config.py's PRIORITY_W1..W5 defaults.
const DEFAULT_WEIGHTS: PriorityWeights = {
  w1_severity: 0.35,
  w2_population: 0.25,
  w3_facility_proximity: 0.2,
  w4_confidence: 0.2,
  w5_route_impact: 0.0,
};

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

  function handleReset() {
    setWeights({ ...DEFAULT_WEIGHTS });
    setStatus("Reset to defaults — click Save to apply.");
  }

  return (
    <div className="ts-scroll" style={{ flex: 1, padding: "32px", maxWidth: "600px", overflowY: "auto" }}>
      <h1 style={{ fontSize: "var(--font-size-xl)", fontWeight: 700, margin: "0 0 6px", letterSpacing: "-0.01em" }}>Settings</h1>
      <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", margin: "0 0 28px", lineHeight: 1.5 }}>
        Priority score weights: priority = w1·sev_score + w2·norm(population_est) + w3·facility_proximity +
        w4·confidence + w5·route_impact. Changes apply to the next analysis you run — they don't recompute whatever
        is currently on screen.
      </p>

      {!weights ? (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>Loading…</p>
      ) : (
        <>
          <div className="ts-card" style={{ padding: "20px 22px" }}>
            {WEIGHT_LABELS.map(({ key, label, hint }, i) => (
              <div key={key} style={{ marginBottom: i < WEIGHT_LABELS.length - 1 ? "22px" : 0 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "2px" }}>
                  <label style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text)", fontWeight: 500 }}>{label}</label>
                  <span className="mono" style={{ fontSize: "var(--font-size-sm)", color: "var(--color-accent)", fontWeight: 600 }}>
                    {weights[key].toFixed(2)}
                  </span>
                </div>
                <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-faint)", margin: "0 0 10px" }}>{hint}</p>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={weights[key]}
                  onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
                  style={{ width: "100%", accentColor: "var(--color-accent)" }}
                />
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
            <button className="ts-btn ts-btn-primary" onClick={handleSave}>
              Save
            </button>
            <button className="ts-btn" onClick={handleReset}>
              <RotateCcw size={13} />
              Reset to defaults
            </button>
          </div>
          {status && (
            <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", marginTop: "12px" }}>{status}</p>
          )}
        </>
      )}
    </div>
  );
}
