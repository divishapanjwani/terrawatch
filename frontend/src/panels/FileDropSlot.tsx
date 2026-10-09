import { useRef, useState } from "react";

const ACCEPTED_EXT = [".tif", ".tiff"];

function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext));
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
    <div style={{ marginBottom: "12px" }}>
      <label style={{ display: "block", fontSize: "var(--font-size-xs)", marginBottom: "4px" }}>
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
          border: `1px dashed ${dragging ? "var(--color-accent)" : "var(--color-border)"}`,
          borderRadius: "var(--radius-sm)",
          background: dragging ? "rgba(47,93,70,0.05)" : "var(--color-panel)",
          padding: "10px",
          fontSize: "var(--font-size-xs)",
          color: file ? "var(--color-text)" : "var(--color-text-secondary)",
          cursor: "pointer",
          textAlign: "center",
          transition: "border-color var(--transition-fast), background var(--transition-fast)",
        }}
      >
        {file ? (
          <span className="mono">{file.name}</span>
        ) : (
          <span>Drop GeoTIFF here or click to choose (.tif, .tiff)</span>
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
