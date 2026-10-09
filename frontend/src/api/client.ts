export const API_BASE = "http://127.0.0.1:8000";

export interface Bounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface AnalysisStatus {
  id: string;
  mode: string;
  status: "pending" | "ready" | "failed";
  progress_step: string;
  error_message: string | null;
  bounds: Bounds | null;
  created_at: string;
}

export async function createAnalysis(
  before: File,
  after: File,
  mode: string
): Promise<{ analysis_id: string }> {
  const form = new FormData();
  form.append("before", before);
  form.append("after", after);
  form.append("mode", mode);

  const res = await fetch(`${API_BASE}/api/analyses`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function getAnalysis(id: string): Promise<AnalysisStatus> {
  const res = await fetch(`${API_BASE}/api/analyses/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch analysis: ${res.status}`);
  }
  return res.json();
}

export function imageryUrl(id: string, which: "before" | "after"): string {
  return `${API_BASE}/api/analyses/${id}/imagery/${which}`;
}

export async function pollUntilReady(
  id: string,
  intervalMs = 800,
  timeoutMs = 60000
): Promise<AnalysisStatus> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const status = await getAnalysis(id);
    if (status.status === "ready" || status.status === "failed") {
      return status;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for analysis to complete");
}
