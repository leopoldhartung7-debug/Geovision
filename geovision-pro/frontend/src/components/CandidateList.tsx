import type { AnalysisResult } from "../types";

const SOURCE_LABEL: Record<string, string> = {
  exif: "GPS-Metadaten (exakt)",
  ocr: "Schildtext (geocodiert)",
  inference: "Bildinferenz (Land/Region)",
};

export default function CandidateList({ result }: { result: AnalysisResult }) {
  const h = result.hierarchy;
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold">Standort-Hypothesen</h2>
        <span className="text-xs px-2 py-1 rounded-full border border-edge text-muted">
          {SOURCE_LABEL[result.location_source] || result.location_source}
        </span>
      </div>

      {/* Hierarchy */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3 text-center text-sm">
        {[["Kontinent", h.continent], ["Land", h.country], ["Region", h.region],
          ["Stadt", h.city], ["Stadtteil", h.district]].map(([k, v]) => (
          <div key={k as string} className="bg-panel2 rounded-lg p-2 border border-edge">
            <div className="text-muted text-[11px]">{k}</div>
            <div className="font-semibold truncate">{(v as string) || "—"}</div>
          </div>
        ))}
      </div>
      {h.note && <p className="text-xs text-muted mb-3">{h.note}</p>}

      {/* Candidates */}
      <div className="space-y-2">
        {result.candidates.map((c) => (
          <div key={c.rank} className="bg-panel2 rounded-lg p-3 border border-edge">
            <div className="flex items-center gap-3">
              <span className="text-muted font-bold w-5">{c.rank}</span>
              <span className="flex-1 font-semibold truncate">{c.label}</span>
              <span className="text-muted text-sm tabular-nums">{Math.round(c.confidence * 100)}%</span>
            </div>
            <div className="bar mt-2"><span style={{ width: `${Math.round(c.confidence * 100)}%` }} /></div>
            {c.reasoning && <p className="text-xs text-muted mt-2">{c.reasoning}</p>}
          </div>
        ))}
        {result.candidates.length === 0 && (
          <p className="text-muted text-sm">Keine Kandidaten ermittelt.</p>
        )}
      </div>

      {result.uncertainty && (
        <div className="mt-3 text-xs text-amber-300/90 bg-amber-500/5 border border-amber-700/40 rounded-lg p-2.5">
          ⚠️ Unsicherheit: {result.uncertainty}
        </div>
      )}
    </div>
  );
}
