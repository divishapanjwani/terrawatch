import { AlertCircle, ShieldCheck, UploadCloud, Users2 } from "lucide-react";

export default function Hero({
  onLoadDemo,
  onUploadOwn,
  demoLoading,
  demoError,
}: {
  onLoadDemo: () => void;
  onUploadOwn: () => void;
  demoLoading: boolean;
  demoError: string | null;
}) {
  return (
    <div
      style={{
        position: "relative",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
        background:
          "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(47,211,193,0.08), transparent 70%), var(--color-bg)",
      }}
    >
      {/* Abstract dimmed "satellite" backdrop: contour lines + a faint grid, built from CSS only. */}
      <svg
        aria-hidden
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.35 }}
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <pattern id="hero-grid" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#22343A" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hero-grid)" />
        {[0, 1, 2, 3].map((i) => (
          <ellipse
            key={i}
            cx="50%"
            cy="45%"
            rx={120 + i * 90}
            ry={80 + i * 60}
            fill="none"
            stroke="#2FD3C1"
            strokeOpacity={0.12 - i * 0.02}
            strokeWidth={1}
          />
        ))}
      </svg>

      <div
        className="ts-fade-up"
        style={{
          position: "relative",
          textAlign: "center",
          maxWidth: "560px",
          padding: "0 24px",
        }}
      >
        <h1
          style={{
            fontSize: "var(--font-size-3xl)",
            fontWeight: 700,
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
            margin: "0 0 12px",
            color: "var(--color-text)",
          }}
        >
          From satellite changes to response priorities
        </h1>
        <p
          style={{
            fontSize: "var(--font-size-base)",
            color: "var(--color-text-secondary)",
            margin: "0 0 32px",
            lineHeight: 1.5,
          }}
        >
          Upload a before/after image pair and TerraWatch finds real changes, explains the false
          alarms, and ranks what to look at first.
        </p>

        <div style={{ display: "flex", gap: "10px", justifyContent: "center", marginBottom: "20px" }}>
          <button className="ts-btn ts-btn-primary" onClick={onLoadDemo} disabled={demoLoading}>
            {demoLoading ? "Loading…" : "Load Wayanad demo"}
          </button>
          <button className="ts-btn" onClick={onUploadOwn}>
            <UploadCloud size={14} />
            Upload your own GeoTIFFs
          </button>
        </div>

        {demoError && (
          <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-danger)", margin: "0 0 16px" }}>
            {demoError}
          </p>
        )}

        <div style={{ display: "flex", gap: "8px", justifyContent: "center", flexWrap: "wrap" }}>
          {[
            { icon: <ShieldCheck size={12} />, label: "Explained false alarms" },
            { icon: <Users2 size={12} />, label: "People & facilities" },
            { icon: <AlertCircle size={12} />, label: "Prevention mode" },
          ].map((chip) => (
            <span
              key={chip.label}
              className="ts-pill ts-pill-neutral"
              style={{ textTransform: "none", letterSpacing: 0, fontWeight: 500, fontSize: "var(--font-size-xs)" }}
            >
              {chip.icon}
              {chip.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
