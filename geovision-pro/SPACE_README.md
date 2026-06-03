---
title: GeoVision Pro
emoji: 🌍
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# GeoVision Pro

KI-Geolocation aus Bildern/Videos. Reihenfolge (verlässlichste Quelle zuerst):
EXIF-GPS → Schildtext (OCR) → **Referenzgalerie** (Bild-Retrieval gegen deine
eigenen Geo-Fotos) → **Picarta-API** (GeoSpy-Klasse, optional) → GeoCLIP →
StreetCLIP-Kontext. Läuft als ein Container (FastAPI serviert die React-App + API).

> Erster Analyse-Request lädt einmalig die Modelle (GeoCLIP + StreetCLIP) — das
> dauert auf der kostenlosen CPU ein paar Minuten, danach sind sie gecached.

## Genauer machen (optional)

**Picarta einschalten (am nächsten an GeoSpy):**
1. Kostenlosen Token holen: https://picarta.ai → Account → API.
2. Im Space: *Settings → Variables and secrets → New secret* →
   Name `GEOVISION_PICARTA_API_TOKEN`, Wert = dein Token → Save.
3. Space neu starten (*Restart*). Treffer erscheinen dann als „Picarta-API".

**Eigene Galerie („Training mit mehr Bildern"):**
Im Panel **„Eigene Galerie"** in der App ein geotaggtes Foto hochladen und Ort
angeben (Ortsname, Koordinaten oder per Foto-GPS) — die App erkennt diese Orte
danach genauer. Je mehr Fotos, desto besser.
> ⚠️ Auf einem kostenlosen Space ohne *persistent storage* gehen die Galerie-
> Fotos beim Neustart/Rebuild verloren. Für dauerhaftes Speichern in den Space-
> Settings **Persistent storage** aktivieren (legt `/data` dauerhaft an).
