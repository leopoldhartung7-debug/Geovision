import { useCallback, useEffect, useState } from "react";
import {
  analyzeBatch, analyzeImage, analyzeVideo, deleteJob, listJobs,
} from "./api";
import type { AnalysisResult, JobListItem } from "./types";
import UploadPanel from "./components/UploadPanel";
import MapView from "./components/MapView";
import CandidateList from "./components/CandidateList";
import Explain from "./components/Explain";
import HistoryPanel from "./components/HistoryPanel";
import ReportButtons from "./components/ReportButtons";

export default function App() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [batch, setBatch] = useState<AnalysisResult[]>([]);
  const [jobs, setJobs] = useState<JobListItem[]>([]);

  const refreshJobs = useCallback(async () => {
    try { setJobs(await listJobs()); } catch { /* ignore */ }
  }, []);

  useEffect(() => { refreshJobs(); }, [refreshJobs]);

  const run = useCallback(async (fn: () => Promise<void>) => {
    setBusy(true); setError("");
    try { await fn(); } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); refreshJobs(); }
  }, [refreshJobs]);

  const onImages = (files: File[]) => run(async () => {
    if (files.length === 1) {
      const r = await analyzeImage(files[0]);
      setResult(r); setBatch([]);
    } else {
      const rs = await analyzeBatch(files);
      setBatch(rs); setResult(rs[0] || null);
    }
  });

  const onVideo = (file: File) => run(async () => {
    const r = await analyzeVideo(file);
    setResult(r); setBatch([]);
  });

  const openJob = (id: number) => run(async () => {
    const r = await fetch(`${import.meta.env.VITE_API_BASE || "/api"}/jobs/${id}`).then((x) => x.json());
    setResult(r); setBatch([]);
  });

  const removeJob = async (id: number) => { await deleteJob(id); refreshJobs(); if (result?.id === id) setResult(null); };

  return (
    <div className="min-h-full">
      <header className="border-b border-edge bg-panel/60 backdrop-blur sticky top-0 z-[1000]">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="font-extrabold text-xl flex items-baseline gap-2">
            Geo<span className="text-accent">Vision</span> Pro
            <span className="text-[10px] font-semibold text-accent border border-accent/40 rounded px-1.5 py-0.5">
              v1.1 · schnell
            </span>
          </div>
          <div className="text-xs text-muted hidden sm:block">
            Land/Region zuverlässig · Stadt nur bei GPS/Schild · transparente Unsicherheit
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-5 grid lg:grid-cols-3 gap-4">
        {/* Left: map + candidates (main focus) */}
        <section className="lg:col-span-2 space-y-4">
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold">Karte</h2>
              {result && <ReportButtons id={result.id} />}
            </div>
            <MapView candidates={result?.candidates ?? []} />
            {result?.model_used && (
              <p className="text-xs text-muted mt-2">Modell: {result.model_used}</p>
            )}
          </div>
          {result && <CandidateList result={result} />}
          {batch.length > 1 && (
            <div className="card">
              <h2 className="font-bold mb-2">Batch-Ergebnisse ({batch.length})</h2>
              <div className="space-y-1 text-sm">
                {batch.map((b, i) => (
                  <button key={i} onClick={() => setResult(b)}
                    className="w-full text-left bg-panel2 border border-edge rounded-lg px-3 py-2 hover:border-accent">
                    <span className="font-semibold">{b.candidates[0]?.label || "—"}</span>
                    <span className="text-muted"> · {b.source_name}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Right: upload + explain + history */}
        <section className="space-y-4">
          <UploadPanel busy={busy} onImages={onImages} onVideo={onVideo} />
          {error && (
            <div className="card border-rose-700/50 text-rose-300 text-sm">Fehler: {error}</div>
          )}
          {result && <Explain result={result} />}
          <HistoryPanel jobs={jobs} onOpen={openJob} onDelete={removeJob} />
        </section>
      </main>

      <footer className="max-w-6xl mx-auto px-4 py-6 text-xs text-muted">
        Keine Personenidentifikation · Kennzeichen nur als Format/Farbe, keine OCR konkreter Nummern ·
        Karte © OpenStreetMap · Geocoding Nominatim
      </footer>
    </div>
  );
}
