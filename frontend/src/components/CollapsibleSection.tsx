import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { forwardRef } from "react";

const CollapsibleSection = forwardRef<
  HTMLDivElement,
  {
    title: string;
    open: boolean;
    onToggle: () => void;
    children: ReactNode;
  }
>(function CollapsibleSection({ title, open, onToggle, children }, ref) {
  return (
    <div ref={ref} style={{ borderBottom: "1px solid var(--color-border)" }}>
      <button className="ts-section-header" onClick={onToggle}>
        <span className="ts-label">{title}</span>
        <ChevronRight size={14} className={`ts-chevron ${open ? "open" : ""}`} />
      </button>
      {open && <div style={{ paddingBottom: "16px" }}>{children}</div>}
    </div>
  );
});

export default CollapsibleSection;
