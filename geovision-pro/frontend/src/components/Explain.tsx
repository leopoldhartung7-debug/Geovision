import type { AnalysisResult } from "../types";

export default function Explain({ result }: { result: AnalysisResult }) {
  return (
    <div className="card">
      <h2 className="font-bold mb-3">Erklärung (Explainable AI)</h2>
      <p className="text-xs text-muted mb-3">
        Gewichte = relative Sicherheit jeder Bildmerkmal-Kategorie. Sie zeigen, welche Hinweise die
        Schätzung getragen haben — keine erfundenen Zahlen.
      </p>
      <div className="space-y-3">
        {result.signals.map((g) => (
          <div key={g.name}>
            <div className="flex justify-between text-sm">
              <span className="font-semibold">{g.name}</span>
              <span className="text-muted tabular-nums">{Math.round(g.weight * 100)}%</span>
            </div>
            <div className="bar mt-1"><span style={{ width: `${Math.round(g.weight * 100)}%` }} /></div>
            <div className="text-xs text-muted mt-1">
              {g.top.map((t) => `${t.label} (${Math.round(t.score * 100)}%)`).join(" · ")}
            </div>
          </div>
        ))}
        {result.signals.length === 0 && <p className="text-muted text-sm">Keine Merkmalsanalyse (z. B. Video).</p>}
      </div>

      {result.ocr_text && (
        <div className="mt-4">
          <div className="font-semibold text-sm mb-1">Erkannter Text (OCR)</div>
          <pre className="text-xs bg-panel2 border border-edge rounded-lg p-2 whitespace-pre-wrap">{result.ocr_text}</pre>
        </div>
      )}

      <div className="mt-4">
        <div className="font-semibold text-sm mb-1">Referenzvergleich</div>
        {result.reference_matches.length > 0 ? (
          <ul className="text-xs text-muted space-y-1">
            {result.reference_matches.map((m) => (
              <li key={m.name} className="flex justify-between">
                <span className="truncate">{m.name}</span>
                <span className="tabular-nums">{Math.round(m.similarity * 100)}%</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted">
            Keine eigene Referenz-Bilddatenbank konfiguriert. Für „ähnliche Bilder weltweit" das Foto
            in eine Bildsuche geben:{" "}
            <a className="text-accent2" href="https://lens.google.com/" target="_blank" rel="noopener">Google Lens</a>.
          </p>
        )}
      </div>
    </div>
  );
}
