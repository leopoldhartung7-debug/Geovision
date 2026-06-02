import type { JobListItem } from "../types";

interface Props {
  jobs: JobListItem[];
  onOpen: (id: number) => void;
  onDelete: (id: number) => void;
}

export default function HistoryPanel({ jobs, onOpen, onDelete }: Props) {
  return (
    <div className="card">
      <h2 className="font-bold mb-3">Verlauf</h2>
      {jobs.length === 0 && <p className="text-muted text-sm">Noch keine Analysen.</p>}
      <div className="space-y-2 max-h-[360px] overflow-auto pr-1">
        {jobs.map((j) => (
          <div key={j.id} className="flex items-center gap-2 bg-panel2 border border-edge rounded-lg p-2">
            <button onClick={() => onOpen(j.id)} className="flex-1 text-left min-w-0">
              <div className="font-semibold text-sm truncate">{j.best_label || "—"}</div>
              <div className="text-xs text-muted">
                {new Date(j.created_at).toLocaleString("de-DE")} · {j.kind} · {j.location_source}
                {j.best_confidence != null && ` · ${Math.round(j.best_confidence * 100)}%`}
              </div>
            </button>
            <button onClick={() => onDelete(j.id)} className="text-rose-400 px-2 text-lg" title="Löschen">×</button>
          </div>
        ))}
      </div>
    </div>
  );
}
