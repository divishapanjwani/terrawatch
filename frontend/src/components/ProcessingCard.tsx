import { Check } from "lucide-react";

const STEP_LABELS: Record<string, string> = {
  validating: "Validating",
  quality_check: "Quality check",
  detecting: "Detecting",
  filtering: "Filtering",
  vectorizing: "Vectorizing",
  impact_analysis: "Impact analysis",
  done: "Done",
};

const FALLBACK_STEPS = [
  "validating",
  "quality_check",
  "detecting",
  "filtering",
  "vectorizing",
  "impact_analysis",
  "done",
];

export default function ProcessingCard({ step, steps }: { step: string; steps: string[] }) {
  const list = steps.length ? steps : FALLBACK_STEPS;
  const currentIdx = list.indexOf(step);

  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div className="ts-card ts-fade-up" style={{ width: "320px", padding: "24px" }}>
        <div className="ts-label" style={{ marginBottom: "16px" }}>
          Processing analysis
        </div>
        {list.map((s, i) => {
          const isDone = currentIdx > i || (currentIdx === -1 && false);
          const isCurrent = s === step;
          return (
            <div
              key={s}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: "7px 0",
              }}
            >
              <span
                style={{
                  width: "18px",
                  height: "18px",
                  borderRadius: "50%",
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: isDone
                    ? "var(--color-accent)"
                    : isCurrent
                      ? "var(--color-accent-soft)"
                      : "var(--color-card)",
                  border: isCurrent ? "1.5px solid var(--color-accent)" : "1px solid var(--color-border)",
                }}
              >
                {isDone ? (
                  <Check size={11} color="#06201c" strokeWidth={3} />
                ) : isCurrent ? (
                  <span
                    className="ts-pulse"
                    style={{
                      width: "6px",
                      height: "6px",
                      borderRadius: "50%",
                      background: "var(--color-accent)",
                    }}
                  />
                ) : null}
              </span>
              <span
                style={{
                  fontSize: "var(--font-size-sm)",
                  fontWeight: isCurrent ? 600 : 400,
                  color: isDone || isCurrent ? "var(--color-text)" : "var(--color-text-faint)",
                }}
              >
                {STEP_LABELS[s] ?? s}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
