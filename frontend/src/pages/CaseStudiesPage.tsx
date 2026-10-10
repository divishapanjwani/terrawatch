import { useEffect, useState } from "react";
import { Calendar, CloudSun, MapPin } from "lucide-react";
import { listCaseStudies } from "../api/client";
import type { CaseStudy } from "../api/client";

const CATEGORY_LABEL: Record<string, string> = {
  landslide: "Landslide",
  glacial_lake_outburst_flood: "Glacial lake outburst flood",
  flood: "Flood",
  urban_growth: "Urban growth",
};

export default function CaseStudiesPage({
  onLoad,
  loadingSlug,
}: {
  onLoad: (slug: string) => void;
  loadingSlug: string | null;
}) {
  const [studies, setStudies] = useState<CaseStudy[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    listCaseStudies()
      .then(setStudies)
      .catch((err) => setListError((err as Error).message));
  }, []);

  return (
    <div className="ts-scroll" style={{ flex: 1, padding: "32px", overflowY: "auto" }}>
      <h1
        style={{
          fontSize: "var(--font-size-xl)",
          fontWeight: 700,
          margin: "0 0 6px",
          letterSpacing: "-0.01em",
        }}
      >
        Case studies
      </h1>
      <p
        style={{
          fontSize: "var(--font-size-sm)",
          color: "var(--color-text-secondary)",
          margin: "0 0 28px",
          lineHeight: 1.5,
          maxWidth: "720px",
        }}
      >
        Real Indian events with pre-fetched, cached Sentinel-2 imagery — one click runs the full pipeline with
        no live Planetary Computer call needed. Coordinates and dates verified against named sources (see{" "}
        <span className="mono">backend/app/case_studies.py</span>).
      </p>

      {listError && (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-danger)" }}>{listError}</p>
      )}

      {!studies ? (
        <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>Loading…</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: "16px",
            maxWidth: "1100px",
          }}
        >
          {studies.map((cs) => (
            <div
              key={cs.slug}
              className="ts-card"
              style={{ overflow: "hidden", display: "flex", flexDirection: "column" }}
            >
              <div
                style={{
                  height: "140px",
                  background: `url(${cs.thumbnail_url}) center/cover no-repeat`,
                  backgroundColor: "var(--color-bg-subtle, #18252A)",
                  position: "relative",
                }}
              >
                <span
                  style={{
                    position: "absolute",
                    top: "8px",
                    left: "8px",
                    fontSize: "10px",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    padding: "3px 8px",
                    borderRadius: "var(--radius-sm)",
                    background: "rgba(11,18,21,0.75)",
                    color: "var(--color-text)",
                  }}
                >
                  {CATEGORY_LABEL[cs.category] ?? cs.category}
                </span>
              </div>
              <div
                style={{
                  padding: "14px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                  flex: 1,
                }}
              >
                <h3 style={{ fontSize: "var(--font-size-md)", fontWeight: 600, margin: 0 }}>{cs.name}</h3>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--color-text-secondary)",
                    fontSize: "var(--font-size-xs)",
                  }}
                >
                  <MapPin size={12} /> {cs.location}
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    color: "var(--color-text-secondary)",
                    fontSize: "var(--font-size-xs)",
                  }}
                >
                  <Calendar size={12} /> {cs.event_date}
                </div>
                <p
                  style={{
                    fontSize: "var(--font-size-xs)",
                    color: "var(--color-text-secondary)",
                    lineHeight: 1.45,
                    margin: "4px 0 8px",
                  }}
                >
                  {cs.description}
                </p>
                {cs.known_scenes && (
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      color: "var(--color-text-faint)",
                      fontSize: "11px",
                      marginBottom: "4px",
                    }}
                  >
                    <CloudSun size={12} />
                    <span className="mono">
                      {cs.known_scenes.before.date} ({cs.known_scenes.before.cloud_cover.toFixed(1)}% cloud) →{" "}
                      {cs.known_scenes.after.date} ({cs.known_scenes.after.cloud_cover.toFixed(1)}% cloud)
                    </span>
                  </div>
                )}
                <div style={{ flex: 1 }} />
                <button
                  className="ts-btn ts-btn-primary"
                  disabled={!cs.cached || loadingSlug !== null}
                  onClick={() => onLoad(cs.slug)}
                  style={{ width: "100%" }}
                >
                  {loadingSlug === cs.slug
                    ? "Loading…"
                    : cs.cached
                      ? "Load case study"
                      : "Not cached — run fetch_case_studies.py"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
