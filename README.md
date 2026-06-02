# GeoVision

Visuelle Standortschätzung aus Fotos — eine einzelne HTML-Datei, die direkt am Handy im Browser läuft (installierbar als PWA), **ohne Server-Setup**.

## Direkt benutzen

Öffne `index.html` einfach im Browser. Für Kamera-Zugriff und PWA-Installation muss die Datei über **HTTPS** geladen werden.

## Was die App ehrlich kann

| Stufe | Funktion | Verlässlichkeit |
|-------|----------|-----------------|
| 1 | **GPS aus EXIF** auslesen → Adresse + **Hotels/Gebäude in der Nähe** (OpenStreetMap/Overpass) | ✅ Exakt, wenn GPS vorhanden. Der einzige Weg zu punktgenauem Haus/Hotel. Viele Bilder (Screenshots, Messenger) haben GPS aber entfernt. |
| 2 | **Bildmerkmale aus Pixeln** mit räumlicher Analyse (Wasser, Sand, Himmel, Vegetation, Bebauung, Schnee …) | ✅ Echte Messungen aus den Pixeln. |
| 3a | **Regionstyp-Heuristik** (regelbasiert, Top-5) | ⚠️ Grobe Tendenz. Konfidenz hart gedeckelt. |
| 3b | **On-Device-KI** (CLIP via transformers.js) — Szene/Biom | ✅ Echtes neuronales Netz, läuft lokal im Browser. Erkennt Strand/Stadt/Berge/Wald zuverlässig. **Kein** konkretes Land/Stadt. |
| 4 | **Optionaler KI-Server** (StreetCLIP) für Land/Stadt | 🔌 Vorbereitet, Backend noch nicht enthalten. |

### Genaue Identifikation (Hotel / Haus / Ort)
- **OCR** (Tesseract.js, on-device): liest sichtbare Schrift (Hotel-/Geschäftsnamen, Schilder) → direkt googeln / in Maps suchen.
- **Bildsuche / Google Lens**: teilt das Foto per Web-Share-API direkt an Google Lens & Co. — der stärkste reale Weg, ein konkretes Gebäude ohne GPS zu finden.

> **Ehrliche Grenze:** Das exakte Hotel/Haus **allein aus den Pixeln** zu erraten, ist technisch nicht möglich — von keiner Software. Die App nutzt deshalb die realen Wege: GPS-Adresse, sichtbarer Text und Bildsuche.

**Grenzen (bewusst eingehalten):** Keine Personenidentifikation. Kennzeichen nur als Format/Farbe, keine OCR konkreter Nummern.

## Funktionen
- Kamera- & Galerie-Upload
- Interaktive Karte (Leaflet + OpenStreetMap) mit Marker bei GPS-Treffer
- Reverse Geocoding (OpenStreetMap Nominatim, max. 1 Anfrage/Sek)
- Begründung: welche Merkmale → welche Einschätzung
- Suchhistorie lokal gespeichert (`localStorage`, überlebt Neustarts)
- CSV-Export der Historie
- Dark Theme, mobil-optimiert

## Abhängigkeiten (via CDN, brauchen Internet beim ersten Laden)
- [Leaflet](https://leafletjs.com/) — Karte
- [exifr](https://github.com/MikeKovarik/exifr) — EXIF/GPS-Parsing
- OpenStreetMap-Tiles & Nominatim — Karte & Ortsnamen

Pixel-Analyse und EXIF funktionieren danach auch offline; **Kartentiles und Ortsnamen brauchen immer Netz.**

## Optionaler KI-Server (noch nicht enthalten)
Die App hat ein Feld für eine Server-URL. Erwartetes Protokoll, falls du später ein StreetCLIP-Backend (z. B. auf Hugging Face Spaces) deployst:

```
POST <server-url>
Content-Type: multipart/form-data
Feld "file" = Bild

Antwort (JSON):
{ "predictions": [ { "label": "Frankreich", "score": 0.82 }, ... ] }
```

Sobald ein solcher Endpoint existiert und die URL eingetragen ist, ruft die App ihn auf — der Client-Teil ist bereits fertig verdrahtet.
