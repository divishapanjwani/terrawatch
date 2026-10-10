import type { ReactNode } from "react";
import { BarChart3, GalleryHorizontal, Layers, Settings as SettingsIcon, SlidersHorizontal } from "lucide-react";

export type RailPage = "analysis" | "case_studies" | "accuracy" | "settings";

function RailButton({
  active,
  title,
  onClick,
  children,
}: {
  active: boolean;
  title: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={title}
      style={{
        width: "36px",
        height: "36px",
        border: "none",
        borderRadius: "var(--radius-sm)",
        background: active ? "var(--color-accent-soft)" : "transparent",
        color: active ? "var(--color-accent)" : "var(--color-text-secondary)",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "background var(--transition-fast), color var(--transition-fast)",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.color = "var(--color-text)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.color = "var(--color-text-secondary)";
      }}
    >
      {children}
    </button>
  );
}

export default function LeftRail({
  page,
  onNavigate,
  onJumpToLayers,
}: {
  page: RailPage;
  onNavigate: (p: RailPage) => void;
  onJumpToLayers: () => void;
}) {
  return (
    <nav
      style={{
        width: "52px",
        flexShrink: 0,
        background: "var(--color-panel)",
        borderRight: "1px solid var(--color-border)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        paddingTop: "16px",
        gap: "8px",
      }}
    >
      <RailButton active={page === "analysis"} title="Analysis" onClick={() => onNavigate("analysis")}>
        <SlidersHorizontal size={18} strokeWidth={1.75} />
      </RailButton>
      <RailButton
        active={page === "case_studies"}
        title="Case studies"
        onClick={() => onNavigate("case_studies")}
      >
        <GalleryHorizontal size={18} strokeWidth={1.75} />
      </RailButton>
      <RailButton active={false} title="Map layers" onClick={onJumpToLayers}>
        <Layers size={18} strokeWidth={1.75} />
      </RailButton>
      <RailButton active={page === "accuracy"} title="Accuracy" onClick={() => onNavigate("accuracy")}>
        <BarChart3 size={18} strokeWidth={1.75} />
      </RailButton>
      <RailButton active={page === "settings"} title="Settings" onClick={() => onNavigate("settings")}>
        <SettingsIcon size={18} strokeWidth={1.75} />
      </RailButton>
    </nav>
  );
}
