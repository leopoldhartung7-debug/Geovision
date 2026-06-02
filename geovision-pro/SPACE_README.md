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

KI-Geolocation aus Bildern/Videos: GeoCLIP sagt echte GPS-Koordinaten voraus,
StreetCLIP liefert Land-/Szenen-Kontext, EXIF-GPS und Ortsschilder (OCR) haben
Vorrang. Läuft hier als ein Container (FastAPI serviert die React-App + API).

> Erster Analyse-Request lädt einmalig die Modelle (GeoCLIP + StreetCLIP) — das
> dauert auf der kostenlosen CPU ein paar Minuten, danach sind sie gecached.
