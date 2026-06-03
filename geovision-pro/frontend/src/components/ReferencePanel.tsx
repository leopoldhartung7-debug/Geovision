import { useCallback, useEffect, useRef, useState } from "react";
import { addReference, listReference } from "../api";
import type { ReferenceList } from "../api";

/**
 * Grow the app's accuracy with your own geotagged photos — the practical,
 * free "train it with more images" path. Pick a photo, say where it was taken
 * (place name OR coordinates OR rely on the photo's own GPS), and add it.
 */
export default function ReferencePanel() {
  const [info, setInfo] = useState<ReferenceList | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [place, setPlace] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try { setInfo(await listReference()); } catch { /* ignore */ }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const add = useCallback(async () => {
    if (!file) { setErr("Bitte zuerst ein Foto wählen."); return; }
    setBusy(true); setErr(""); setMsg("");
    try {
      // Allow "lat, lon" typed directly into the place field.
      const m = place.match(/^\s*(-?\d{1,2}\.\d+)\s*[,; ]\s*(-?\d{1,3}\.\d+)\s*$/);
      const opts = m
        ? { lat: parseFloat(m[1]), lon: parseFloat(m[2]) }
        : { place: place.trim() || undefined };
      const r = await addReference(file, opts);
      setMsg(`Hinzugefügt ✓ (${r.reference_images} Fotos in der Galerie, Quelle: ${r.source})`);
      setFile(null); setPlace("");
      if (inputRef.current) inputRef.current.value = "";
      refresh();
    } catch (e) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  }, [file, place, refresh]);

  return (
    <div className="card">
      <h2 className="font-bold mb-1">Eigene Galerie (genauer machen)</h2>
      <p className="text-xs text-muted mb-3">
        Füge geotaggte Fotos hinzu — die App erkennt diese Orte danach deutlich
        genauer. Je mehr, desto besser.
        {info != null && (
          <> {" "}<span className="text-accent">{info.reference_images} Fotos</span>
            {" "}({info.reference_geolocated} mit Ort).</>
        )}
      </p>

      <input
        ref={inputRef}
        type="file"
        accept="image/*,.heic,.heif"
        className="block w-full text-sm mb-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg
          file:border-0 file:bg-accent file:text-black file:font-semibold"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <input
        type="text"
        value={place}
        onChange={(e) => setPlace(e.target.value)}
        placeholder='Ort (z. B. "Marienplatz, München") oder "48.1372, 11.5755"'
        className="w-full bg-panel2 border border-edge rounded-lg px-3 py-2 text-sm mb-1"
      />
      <p className="text-[11px] text-muted mb-2">
        Leer lassen, wenn das Foto bereits GPS-Daten enthält.
      </p>

      <button
        onClick={add}
        disabled={busy}
        className="w-full bg-accent text-black font-semibold rounded-lg py-2 text-sm
          disabled:opacity-50"
      >
        {busy ? "Füge hinzu …" : "Zur Galerie hinzufügen"}
      </button>

      {msg && <div className="text-emerald-400 text-xs mt-2">{msg}</div>}
      {err && <div className="text-rose-300 text-xs mt-2">Fehler: {err}</div>}

      {info && info.entries.length > 0 && (
        <div className="mt-3 max-h-32 overflow-auto text-xs text-muted space-y-1">
          {info.entries.slice().reverse().map((e, i) => (
            <div key={i} className="flex justify-between gap-2">
              <span className="truncate">{e.name}</span>
              <span className="shrink-0">
                {e.lat != null && e.lon != null ? `${e.lat.toFixed(3)}, ${e.lon.toFixed(3)}` : "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
