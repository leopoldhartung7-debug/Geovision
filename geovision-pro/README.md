# GeoVision Pro

Professionelle Geolocation-KI: schätzt aus Bildern/Videos den wahrscheinlichsten
Aufnahmeort und **begründet** jede Schlussfolgerung — mit transparenter Unsicherheit.

> **GeoSpy-Ansatz, ehrlich umgesetzt.** Kern ist **GeoCLIP** (NeurIPS 2023), das — wie
> kommerzielle Tools (GeoSpy) — **echte GPS-Koordinaten** vorhersagt (Top-k mit
> Wahrscheinlichkeiten) und sie per Reverse-Geocoding zu **Stadt → Region → Land** auflöst.
> StreetCLIP liefert ergänzenden Land-/Szenen-Kontext. **GPS-Metadaten** und **lesbare
> Ortsschilder** haben weiterhin Vorrang (exakt). Wichtig & ehrlich: GeoCLIP-Koordinaten sind
> eine **Modell-Schätzung** (kein GPS) — die Stadt-Ebene kann ungenau sein; die UI weist Streuung
> und Unsicherheit offen aus. Eine straßengenaue Garantie allein aus Pixeln gibt es nicht — das ist
> eine Forschungsgrenze, kein Bug. PIGEON/PIGEOTTO sind stärker, aber ihre Gewichte sind nicht frei nutzbar.

**Entscheidungsreihenfolge für den Ort:** `EXIF-GPS` (exakt) → `Ortsschild→Geocoding` (real) →
`GeoCLIP-Koordinaten` (Modell-Schätzung: Stadt/Region/Land) → `StreetCLIP` (nur Land/Region).
GeoCLIP ist optional: Lädt das Modell nicht, fällt die Pipeline automatisch auf StreetCLIP zurück.

## Architektur

```
geovision-pro/
├── backend/                 FastAPI + PyTorch (GeoCLIP + StreetCLIP) + SQLAlchemy
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

## Online stellen (Handy-Link, ohne Terminal)

Du willst nur einen Link, den du am Handy öffnest? Deploy auf **Hugging Face Spaces** (gratis),
komplett im Browser:

1. Account anlegen: <https://huggingface.co> → **Write-Token** erstellen unter
   <https://huggingface.co/settings/tokens>
2. In diesem GitHub-Repo: **Settings → Secrets and variables → Actions → New repository secret**,
   Name `HF_TOKEN`, Wert = dein Token
3. **Actions**-Tab → Workflow **„Deploy to Hugging Face Space"** → **Run workflow** →
   HF-Benutzername eingeben → **Run**
4. Nach dem Build erreichbar unter **`https://<dein-user>-geovision-pro.hf.space`**

(Die Action baut alles in *einen* Container — FastAPI liefert die React-App + API; SQLite statt
Postgres. Erster Analyse-Request lädt einmalig die Modelle.)

## Schnellstart (Docker, lokal)

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
