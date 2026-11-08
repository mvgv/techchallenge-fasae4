CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE patients (
  patient_id   TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  bed          TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE media (
  media_id      UUID PRIMARY KEY,
  patient_id    TEXT NOT NULL REFERENCES patients(patient_id),
  kind          TEXT NOT NULL CHECK (kind IN ('video','audio','document')),
  mode          TEXT,
  exercise      TEXT,
  camera        TEXT,
  storage_uri   TEXT NOT NULL,
  original_name TEXT,
  recorded_at   TIMESTAMPTZ NOT NULL,
  status        TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','processing','done','failed')),
  error         TEXT,
  artifacts     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vitals (
  patient_id    TEXT NOT NULL,
  ts            TIMESTAMPTZ NOT NULL,
  hr REAL, sbp REAL, dbp REAL, spo2 REAL, rr REAL, temp REAL,
  consciousness TEXT,
  on_oxygen     BOOLEAN,
  news2         INTEGER,
  PRIMARY KEY (patient_id, ts)
);
SELECT create_hypertable('vitals', 'ts');

CREATE TABLE prescriptions (
  rx_id       TEXT PRIMARY KEY,
  patient_id  TEXT NOT NULL,
  ts          TIMESTAMPTZ NOT NULL,
  drug        TEXT NOT NULL,
  drug_norm   TEXT NOT NULL,
  dose        REAL,
  unit        TEXT,
  route       TEXT,
  frequency   TEXT,
  action      TEXT NOT NULL CHECK (action IN ('start','change','stop'))
);
CREATE INDEX ON prescriptions (patient_id, ts);

CREATE TABLE movement (
  patient_id     TEXT NOT NULL,
  ts             TIMESTAMPTZ NOT NULL,
  activity_count REAL NOT NULL,
  in_bed         BOOLEAN,
  source         TEXT NOT NULL,
  PRIMARY KEY (patient_id, ts, source)
);
SELECT create_hypertable('movement', 'ts');

CREATE TABLE transcripts (
  media_id   UUID PRIMARY KEY REFERENCES media(media_id),
  language   TEXT NOT NULL,
  segments   JSONB NOT NULL,
  analysis   JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE evidence (
  evidence_id   UUID PRIMARY KEY,
  patient_id    TEXT NOT NULL,
  modality      TEXT NOT NULL,
  type          TEXT NOT NULL,
  score         REAL NOT NULL,
  severity      TEXT NOT NULL,
  ts_start      TIMESTAMPTZ NOT NULL,
  ts_end        TIMESTAMPTZ,
  explanation   TEXT NOT NULL,
  source_ref    TEXT,
  model_name    TEXT NOT NULL,
  model_version TEXT NOT NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON evidence (patient_id, ts_start DESC);

CREATE TABLE alerts (
  alert_id     UUID PRIMARY KEY,
  patient_id   TEXT NOT NULL,
  level        TEXT NOT NULL CHECK (level IN ('info','warning','critical')),
  risk_score   REAL NOT NULL,
  title        TEXT NOT NULL,
  summary      TEXT NOT NULL,
  evidence_ids UUID[] NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open'
               CHECK (status IN ('open','acknowledged','dismissed','resolved')),
  escalated    BOOLEAN NOT NULL DEFAULT false,
  event_ts     TIMESTAMPTZ NOT NULL,          -- tempo do evento que gerou o alerta
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  acked_by     TEXT,
  acked_at     TIMESTAMPTZ,
  ack_note     TEXT
);
CREATE INDEX ON alerts (patient_id, status);

CREATE TABLE risk_snapshots (
  patient_id    TEXT NOT NULL,
  ts            TIMESTAMPTZ NOT NULL,
  risk_score    REAL NOT NULL,
  level         TEXT NOT NULL,
  contributions JSONB NOT NULL,
  PRIMARY KEY (patient_id, ts)
);
SELECT create_hypertable('risk_snapshots', 'ts');
