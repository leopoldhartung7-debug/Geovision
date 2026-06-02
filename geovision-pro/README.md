# GeoVision Pro

Professionelle Geolocation-KI: schätzt aus Bildern/Videos den wahrscheinlichsten
Aufnahmeort und **begründet** jede Schlussfolgerung — mit transparenter Unsicherheit.

> **Ehrlichkeit zuerst.** Der Bild-KI-Kern (StreetCLIP) liefert **Kontinent → Land → grobe Region**
> zuverlässig. **Stadt/Stadtteil** werden **nur** ausgegeben, wenn sie aus **GPS-Metadaten** oder
> einem **lesbaren Ortsschild** stammen — sonst bleiben sie bewusst leer („nicht bestimmbar") statt
> geraten. Straßengenaue Identifikation allein aus Pixeln ist nicht möglich; das ist eine
> Forschungsgrenze, kein Bug.

## Architektur

```
geovision-pro/
├── backend/                 FastAPI + PyTorch (StreetCLIP) + SQLAlchemy
│   ├── app/
│   │   ├── main.py          App-Einstieg, Router-Registrierung
│   │   ├── config.py        Settings (ENV: GEOVISION_*)
│   │   ├── database.py      Async-Engine/Session
│   │   ├── models.py        ORM: analyses, candidates
│   │   ├── schemas.py       Pydantic-Schemas (API)
│   │   ├── routers/         analyze, jobs, reports, health
│   │   ├── services/        exif, geocode, vision, ocr, video, fusion, report, reference, labels
│   │   └── core/            logging, cache
│   ├── sql/schema.sql       Produktions-Schema (PostgreSQL)
│   ├── tests/               Pytests (ohne Modell-Download)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                React + Vite + TypeScript + Tailwind + Leaflet
│   ├── src/
│   │   ├── App.tsx          Dashboard (Karte im Fokus)
│   │   ├── api.ts           API-Client
│   │   ├── types.ts         Typen (spiegeln Pydantic-Schemas)
│   │   └── components/      MapView, UploadPanel, CandidateList, Explain, HistoryPanel, ReportButtons
│   ├── nginx.conf           SPA + /api-Proxy
│   └── Dockerfile
├── docker-compose.yml       db + backend + frontend
└── .env.example
```

## Schnellstart (Docker, empfohlen)

```bash
cd geovision-pro
cp .env.example .env          # optional: GEOVISION_NOMINATIM_EMAIL setzen
docker compose up --build
```

- Frontend: <http://localhost:8080>
- API-Docs (Swagger): <http://localhost:8000/docs>
- Beim **ersten** Bild lädt das Modell (StreetCLIP ~600 MB) einmalig in das `models`-Volume.
  Wer es kleiner mag: in `.env` `GEOVISION_VISION_MODEL=openai/clip-vit-base-patch32`.

## Lokale Entwicklung (ohne Docker)

**Backend**
```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# OCR optional: System-Paket tesseract-ocr (+ -deu -eng) installieren
export GEOVISION_DATABASE_URL="postgresql+asyncpg://geovision:geovision@localhost:5432/geovision"
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 , /api wird auf :8000 geproxyt
```

**Tests** (kein Modell nötig)
```bash
cd backend && pip install pytest aiosqlite httpx && pytest
```

## Produktions-Build

```bash
# Backend-Image
docker build -t geovision-backend ./backend
# Frontend-Image (statisches Bundle via nginx)
docker build -t geovision-frontend ./frontend
```
- Für GPU: Backend-Image auf ein `nvidia/cuda`-Basisimage umstellen und CUDA-Torch
  installieren; `GEOVISION_DEVICE=cuda`.
- PostgreSQL produktiv: `sql/schema.sql` ausführen (oder Alembic), nicht `create_all`.
- Nominatim: bei höherem Volumen eigenen Nominatim-Server betreiben und
  `GEOVISION_NOMINATIM_URL` setzen (öffentliche Instanz hat Rate-Limits).

## API (Auszug)

| Methode | Pfad | Zweck |
|--------|------|-------|
| POST | `/api/analyze/image` | Einzelbild (multipart `file`) |
| POST | `/api/analyze/batch` | Mehrere Bilder (`files[]`) |
| POST | `/api/analyze/video` | Video (`file`) → Frame-Konsens |
| GET  | `/api/jobs` | Verlauf |
| GET  | `/api/jobs/{id}` | Einzelergebnis |
| GET  | `/api/report/{id}.pdf\|csv\|json` | Berichtsexport |
| GET  | `/api/status` | Modell-/OCR-/Referenz-Status |

## Was ehrlich (nicht) geht

| Anforderung | Umsetzung |
|---|---|
| Land / grobe Region aus Bild | ✅ StreetCLIP zero-shot |
| Szene/Architektur/Klima-Hinweise + Gewichte | ✅ echte CLIP-Scores |
| Stadt / Stadtteil / Adresse | ✅ **nur** aus GPS-EXIF oder lesbarem Schild (OCR→Geocoding) |
| Top-10 + Begründung + Unsicherheit | ✅ |
| Video → Aufnahmeort | ✅ Frame-Konsens (✗ keine erfundene „Route") |
| „Ähnliche Bilder weltweit" | ✅ gegen **eigenen** Referenzordner; sonst Google-Lens-Weiterleitung (kein Fake-Datensatz) |
| Straßengenaue Lage allein aus Pixeln | ❌ technisch nicht zuverlässig — wird transparent ausgewiesen |
