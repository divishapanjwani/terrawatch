import { useRef, useState } from "react";
import { CheckCircle2, UploadCloud } from "lucide-react";

const ACCEPTED_EXT = [".tif", ".tiff"];

function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext));
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  label: string;
  file: File | null;
  onChange: (file: File | null) => void;
}

export default function FileDropSlot({ label, file, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleFiles(files: FileList | null) {
    const f = files?.[0];
    if (!f) return;
    if (!isAccepted(f)) return;
    onChange(f);
  }

  return (
    <div style={{ marginBottom: "10px" }}>
      <label className="ts-label" style={{ display: "block", marginBottom: "6px" }}>
        {label}
      </label>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        style={{
          border: `1px dashed ${dragging ? "var(--color-accent)" : file ? "var(--color-accent-border)" : "var(--color-border)"}`,
          borderRadius: "var(--radius-sm)",
          background: dragging
            ? "var(--color-accent-soft)"
            : file
              ? "rgba(47,211,193,0.05)"
              : "var(--color-panel)",
          padding: "12px",
          fontSize: "var(--font-size-xs)",
          cursor: "pointer",
          transition: "border-color var(--transition-fast), background var(--transition-fast)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        {file ? (
          <>
            <CheckCircle2 size={16} color="var(--color-accent)" style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div
                className="mono"
                style={{
                  color: "var(--color-text)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {file.name}
              </div>
              <div style={{ color: "var(--color-text-secondary)", marginTop: "1px" }}>
                {formatSize(file.size)}
              </div>
            </div>
          </>
        ) : (
          <>
            <UploadCloud size={16} color="var(--color-text-secondary)" style={{ flexShrink: 0 }} />
            <span style={{ color: "var(--color-text-secondary)" }}>Drop GeoTIFF here or click to choose</span>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".tif,.tiff"
        onChange={(e) => handleFiles(e.target.files)}
        style={{ display: "none" }}
      />
    </div>
  );
}
