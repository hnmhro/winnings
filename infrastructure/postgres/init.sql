CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Teilnahme-Profile
CREATE TABLE profiles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    birth_date  DATE,
    address     JSONB,
    phone       TEXT,
    active      BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Gefundene Gewinnspiele
CREATE TABLE contests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url                 TEXT UNIQUE NOT NULL,
    title               TEXT,
    source              TEXT,
    prize_description   TEXT,
    estimated_value     NUMERIC(12, 2),
    deadline            TIMESTAMPTZ,
    participation_type  TEXT CHECK (participation_type IN ('form', 'email', 'social', 'unknown')),
    trust_score         FLOAT CHECK (trust_score >= 0 AND trust_score <= 1),
    requirements        JSONB DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'found'
                            CHECK (status IN ('found', 'queued', 'participating', 'done', 'won', 'lost', 'skipped', 'error')),
    found_at            TIMESTAMPTZ DEFAULT NOW(),
    participated_at     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_contests_status   ON contests (status);
CREATE INDEX idx_contests_deadline ON contests (deadline);
CREATE INDEX idx_contests_source   ON contests (source);

-- Teilnahme-Protokoll
CREATE TABLE participations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contest_id      UUID NOT NULL REFERENCES contests (id) ON DELETE CASCADE,
    profile_id      UUID REFERENCES profiles (id),
    method          TEXT,
    success         BOOLEAN,
    error_message   TEXT,
    screenshot_path TEXT,
    participated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_participations_contest ON participations (contest_id);

-- E-Mail-Einträge
CREATE TABLE emails (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contest_id       UUID REFERENCES contests (id),
    message_id       TEXT UNIQUE,
    subject          TEXT,
    sender           TEXT,
    classification   TEXT CHECK (classification IN ('WIN_NOTIFICATION', 'CONFIRMATION', 'NEWSLETTER', 'SPAM', 'UNKNOWN')),
    win_description  TEXT,
    win_value        NUMERIC(12, 2),
    action_required  TEXT,
    action_deadline  TIMESTAMPTZ,
    notified         BOOLEAN DEFAULT false,
    raw_body         TEXT,
    received_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_emails_classification ON emails (classification);
CREATE INDEX idx_emails_notified       ON emails (notified) WHERE notified = false;

-- Scraper-Quellen
CREATE TABLE sources (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    type        TEXT CHECK (type IN ('portal', 'rss', 'social', 'search')),
    active      BOOLEAN DEFAULT true,
    last_scraped TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Standard-Quellen eintragen
INSERT INTO sources (name, url, type) VALUES
    ('Gewinnspiele.de', 'https://www.gewinnspiele.de', 'portal'),
    ('Sweepstake RSS', 'https://www.lottobay.de/feed/', 'rss');

-- System-Logs
CREATE TABLE system_logs (
    id          BIGSERIAL PRIMARY KEY,
    service     TEXT NOT NULL,
    level       TEXT CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    message     TEXT NOT NULL,
    details     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_logs_service ON system_logs (service, created_at DESC);
