-- GeoVision Pro — PostgreSQL schema (production reference).
-- The app can also create these via SQLAlchemy on startup (dev convenience),
-- but for production run this file or an Alembic migration.

CREATE TABLE IF NOT EXISTS analyses (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind            VARCHAR(16) NOT NULL DEFAULT 'image',
    source_name     VARCHAR(255) NOT NULL DEFAULT '',
    best_label      VARCHAR(255),
    best_lat        DOUBLE PRECISION,
    best_lon        DOUBLE PRECISION,
    best_confidence DOUBLE PRECISION,
    location_source VARCHAR(32) NOT NULL DEFAULT 'inference',
    result          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses (created_at DESC);

CREATE TABLE IF NOT EXISTS candidates (
    id          SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES analyses (id) ON DELETE CASCADE,
    rank        INTEGER NOT NULL,
    label       VARCHAR(255) NOT NULL,
    confidence  DOUBLE PRECISION NOT NULL,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    reasoning   TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_candidates_analysis_id ON candidates (analysis_id);
