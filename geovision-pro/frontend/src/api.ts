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

export interface ReferenceEntry { name: string; lat: number | null; lon: number | null; }
export interface ReferenceList {
  reference_images: number;
  reference_geolocated: number;
  entries: ReferenceEntry[];
}

export async function listReference(): Promise<ReferenceList> {
  return handle(await fetch(`${BASE}/reference/list`));
}

export async function addReference(
  file: File,
  opts: { place?: string; lat?: number; lon?: number },
): Promise<Record<string, unknown>> {
  const fd = new FormData();
  fd.append("file", file);
  if (opts.place) fd.append("place", opts.place);
  if (opts.lat !== undefined && !Number.isNaN(opts.lat)) fd.append("lat", String(opts.lat));
  if (opts.lon !== undefined && !Number.isNaN(opts.lon)) fd.append("lon", String(opts.lon));
  return handle(await fetch(`${BASE}/reference/add`, { method: "POST", body: fd }));
}
