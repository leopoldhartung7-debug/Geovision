import type { AnalysisResult, JobListItem } from "./types";

const BASE = import.meta.env.VITE_API_BASE || "/api";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function analyzeImage(file: File): Promise<AnalysisResult> {
  const fd = new FormData();
  fd.append("file", file);
  return handle(await fetch(`${BASE}/analyze/image`, { method: "POST", body: fd }));
}

export async function analyzeBatch(files: File[]): Promise<AnalysisResult[]> {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  return handle(await fetch(`${BASE}/analyze/batch`, { method: "POST", body: fd }));
}

export async function analyzeVideo(file: File): Promise<AnalysisResult> {
  const fd = new FormData();
  fd.append("file", file);
  return handle(await fetch(`${BASE}/analyze/video`, { method: "POST", body: fd }));
}

export async function listJobs(limit = 50): Promise<JobListItem[]> {
  return handle(await fetch(`${BASE}/jobs?limit=${limit}`));
}

export async function deleteJob(id: number): Promise<void> {
  await fetch(`${BASE}/jobs/${id}`, { method: "DELETE" });
}

export function reportUrl(id: number, fmt: "pdf" | "csv" | "json"): string {
  return `${BASE}/report/${id}.${fmt}`;
}

export async function getStatus(): Promise<Record<string, unknown>> {
  return handle(await fetch(`${BASE}/status`));
}
