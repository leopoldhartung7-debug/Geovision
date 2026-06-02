# GeoVision Pro — Architektur

## Überblick

```
                 ┌──────────────┐      multipart       ┌──────────────────────────┐
   Browser  ───▶ │  React SPA   │ ───────────────────▶ │   FastAPI (async)        │
 (Dashboard)     │  Leaflet-Map │ ◀─────────────────── │   /api/analyze/*         │
                 └──────────────┘     JSON-Result       │   /api/jobs, /report     │
                                                        └─────────┬────────────────┘
                                                                  │
              ┌───────────────────────────────────────────────────┼───────────────┐
              ▼                         ▼                          ▼               ▼
        EXIF/GPS (Pillow)      Vision (StreetCLIP/CLIP)        OCR (Tesseract)   Geocode
        exakter Ort            Land/Region + Signale           Schildtext        (Nominatim)
              │                         │                          │               │
              └───────────────┬─────────┴──────────────┬───────────┘               │
                              ▼                         ▼                           │
                        Fusion-Engine  ──────────────────────────────────────────▶ │
                  (Quelle wählen, Hierarchie, Top-10, Gewichte, Unsicherheit)       │
                              │                                                     │
                              ▼                                                     ▼
                       PostgreSQL (analyses, candidates)                    Cache (TTL/LRU)
```

## Analyse-Pipeline (Bild)

1. **Decode** (`services/exif.open_image`) — JPG/PNG/WEBP/HEIC (pillow-heif).
2. **EXIF/GPS** (`services/exif.extract_gps`) — exakte Koordinaten, falls vorhanden.
3. **Vision** (`services/vision.VisionEngine`) — ein CLIP-Forward liefert ein
   Bild-Embedding; daraus per Text-Prompt-Vergleich:
   - **Länder-Ranking** (zero-shot über `labels.COUNTRY_NAMES`),
   - **Signalgruppen** (Landschaft/Architektur/Infrastruktur/Klima).
   Text-Embeddings sind gecacht; pro Bild fällt nur **ein** Image-Forward an.
4. **OCR** (`services/ocr`) — optional; Schildtext → Geocoding-Kandidaten.
5. **Fusion** (`services/fusion.analyze_image`) — wählt die **zuverlässigste**
   Standortquelle (EXIF > OCR > Inferenz), baut Hierarchie + Top-10 + Gewichte
   + Unsicherheitstext.
6. **Persistenz** — Ergebnis als Zeile in `analyses` (+ `candidates`), JSON in `result`.

## Explainability

Jede Signalgruppe trägt mit ihrem **Top-Score** zur Gewichtung bei; die Gewichte
werden über alle Gruppen normiert (Summe = 100 %). So zeigt das UI ehrlich, *welche*
Bildhinweise die Schätzung getragen haben — keine erfundenen Prozentzahlen.

## Unsicherheit als Feature

- **EXIF** → „sehr gering" (Standort ist gemessen, nicht geschätzt).
- **OCR** → „mittel" (hängt davon ab, ob der Text der Aufnahmeort ist).
- **Inferenz** → „hoch" (Land/Region; Abstand Top-1↔Top-2 wird ausgewiesen).

## Performance

- **Modell-Singleton** + Lazy-Load; Gewichte im `models`-Volume gecacht.
- **Text-Embedding-Cache** (Prompts ändern sich nicht).
- CPU-bound Inferenz läuft in `asyncio.to_thread`, blockiert die Event-Loop nicht.
- **Geocode-Cache** (TTL/LRU) + 1 req/s Rate-Limit gegen Nominatim.
- **Batch**: sequentiell pro Bild (vermeidet OOM bei großem Modell);
  für Durchsatz horizontal skalieren (mehrere Backend-Replicas hinter LB).

## Sicherheits-/Ethik-Grenzen (im Code verankert)

- Keine Personenidentifikation.
- Kennzeichen nur als Format/Farbe denkbar — **keine** OCR konkreter Nummern.
- Kein erfundener „globaler Bild-Datensatz"; Referenzvergleich nur gegen
  selbst bereitgestellte Bilder, sonst Lens-Weiterleitung.

## Erweiterungspunkte

- **Region/Stadt-Inferenz verbessern:** zusätzliche StreetCLIP-Prompts pro Land
  (Regionen) und hierarchisches Re-Ranking.
- **Reverse-Image-Search:** eigene Vektordatenbank (z. B. pgvector) über die
  vorhandenen Embeddings — Tabelle `analyses.result` enthält bereits die Signale.
- **Worker-Queue** (Celery/RQ) für große Batches/Videos statt Inline-Verarbeitung.
