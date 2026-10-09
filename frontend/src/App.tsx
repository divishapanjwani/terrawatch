import { useState } from "react";
import "./styles/tokens.css";
import "./App.css";
import CompareMap from "./map/CompareMap";
import FileDropSlot from "./panels/FileDropSlot";
import { createAnalysis, imageryUrl, pollUntilReady } from "./api/client";
import type { AnalysisStatus } from "./api/client";

type AppState =
  | { phase: "empty" }
  | { phase: "uploading" }
  | { phase: "processing"; id: string }
  | { phase: "ready"; analysis: AnalysisStatus }
  | { phase: "error"; message: string };

export default function App() {
  const [state, setState] = useState<AppState>({ phase: "empty" });
  const [beforeFile, setBeforeFile] = useState<File | null>(null);
  const [afterFile, setAfterFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"disaster" | "prevention">("disaster");

  async function handleSubmit() {
    if (!beforeFile || !afterFile) return;
    setState({ phase: "uploading" });
    try {
      const { analysis_id } = await createAnalysis(beforeFile, afterFile, mode);
      setState({ phase: "processing", id: analysis_id });
      const analysis = await pollUntilReady(analysis_id);
      if (analysis.status === "failed") {
        setState({ phase: "error", message: analysis.error_message ?? "Analysis failed" });
      } else {
        setState({ phase: "ready", analysis });
      }
    } catch (err) {
      setState({ phase: "error", message: (err as Error).message });
    }
  }

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw" }}>
      <nav
        style={{
          width: "56px",
          background: "var(--color-panel)",
          borderRight: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          paddingTop: "12px",
          gap: "16px",
        }}
      >
        <div
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "var(--radius-sm)",
            background: "var(--color-accent)",
          }}
          title="TerraWatch"
        />
      </nav>

      <aside
        style={{
          width: "320px",
          background: "var(--color-panel)",
          borderRight: "1px solid var(--color-border)",
          padding: "16px",
          overflowY: "auto",
        }}
      >
        <h1 style={{ fontSize: "var(--font-size-lg)", margin: "0 0 4px" }}>TerraWatch</h1>
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)", margin: "0 0 20px" }}>
          Satellite change intelligence
        </p>

        <section style={{ marginBottom: "20px" }}>
          <h2 style={{ fontSize: "var(--font-size-sm)", margin: "0 0 8px", color: "var(--color-text-secondary)" }}>
            New analysis
          </h2>

          <FileDropSlot label="Before image (GeoTIFF)" file={beforeFile} onChange={setBeforeFile} />
          <FileDropSlot label="After image (GeoTIFF)" file={afterFile} onChange={setAfterFile} />

          <label style={{ display: "block", fontSize: "var(--font-size-xs)", marginBottom: "4px" }}>
            Mode
          </label>
          <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
            {(["disaster", "prevention"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  flex: 1,
                  padding: "6px 8px",
                  fontSize: "var(--font-size-xs)",
                  borderRadius: "var(--radius-sm)",
                  border: `1px solid ${mode === m ? "var(--color-accent)" : "var(--color-border)"}`,
                  background: mode === m ? "var(--color-accent)" : "white",
                  color: mode === m ? "white" : "var(--color-text)",
                  cursor: "pointer",
                  textTransform: "capitalize",
                }}
              >
                {m}
              </button>
            ))}
          </div>

          <button
            onClick={handleSubmit}
            disabled={!beforeFile || !afterFile || state.phase === "uploading" || state.phase === "processing"}
            style={{
              width: "100%",
              padding: "8px",
              fontSize: "var(--font-size-sm)",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--color-accent)",
              color: "white",
              cursor: "pointer",
              opacity: !beforeFile || !afterFile ? 0.5 : 1,
            }}
          >
            {state.phase === "uploading" || state.phase === "processing" ? "Processing…" : "Run analysis"}
          </button>
        </section>

        {state.phase === "processing" && (
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
            Validating, reprojecting, and generating previews…
          </p>
        )}
        {state.phase === "error" && (
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-danger)" }}>{state.message}</p>
        )}
        {state.phase === "ready" && (
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
            Analysis <span className="mono">{state.analysis.id}</span> ready.
          </p>
        )}
      </aside>

      <main style={{ flex: 1, position: "relative", background: "var(--color-bg)" }}>
        {state.phase === "ready" && state.analysis.bounds ? (
          <CompareMap
            beforeUrl={imageryUrl(state.analysis.id, "before")}
            afterUrl={imageryUrl(state.analysis.id, "after")}
            bounds={state.analysis.bounds}
          />
        ) : (
          <div
            style={{
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "column",
              color: "var(--color-text-secondary)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            <p>Upload a before/after GeoTIFF pair to begin.</p>
          </div>
        )}
      </main>
    </div>
  );
}
