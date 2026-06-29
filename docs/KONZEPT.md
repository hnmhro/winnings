# Winnings – Automatisiertes Gewinnspiel-System

## Ziel

Vollautomatisiertes System, das:
1. Das Internet nach Gewinnspielen durchsucht
2. Automatisch daran teilnimmt
3. Das E-Mail-Postfach verwaltet und Gewinnbenachrichtigungen erkennt
4. Den Nutzer bei einem Gewinn benachrichtigt

---

## Architektur-Überblick

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network                           │
│                                                                 │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │   Scraper   │   │ Participant  │   │   Email Manager     │  │
│  │  Service    │──▶│   Service   │   │     Service         │  │
│  │             │   │             │   │                     │  │
│  │ - Sucht     │   │ - Füllt     │   │ - Liest Postfach    │  │
│  │   Gewinn-   │   │   Formulare │   │ - Erkennt Gewinn-   │  │
│  │   spiele    │   │   aus       │   │   benachrichtigungen│  │
│  │ - Bewertet  │   │ - Löst      │   │ - Archiviert Spam   │  │
│  │   Qualität  │   │   CAPTCHAs  │   │                     │  │
│  └──────┬──────┘   └──────┬──────┘   └──────────┬──────────┘  │
│         │                 │                      │             │
│         └─────────────────┴──────────────────────┘            │
│                           │                                    │
│                    ┌──────▼──────┐                             │
│                    │  Message    │                             │
│                    │  Queue      │                             │
│                    │  (Redis)    │                             │
│                    └──────┬──────┘                             │
│                           │                                    │
│         ┌─────────────────┼─────────────────┐                 │
│         │                 │                 │                 │
│  ┌──────▼──────┐   ┌──────▼──────┐  ┌──────▼──────┐          │
│  │  Scheduler  │   │  Notifier   │  │  Database   │          │
│  │  Service    │   │  Service    │  │ (PostgreSQL) │          │
│  │             │   │             │  │             │          │
│  │ - Cron-Jobs │   │ - Telegram  │  │ - Gewinnsp. │          │
│  │ - Planung   │   │ - E-Mail    │  │ - Status    │          │
│  │ - Limits    │   │ - Push      │  │ - Profile   │          │
│  └─────────────┘   └─────────────┘  └─────────────┘          │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                   Dashboard (Web UI)                    │  │
│  │  FastAPI Backend + Next.js Frontend + nginx             │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Services im Detail

### 1. Scraper Service

**Aufgabe:** Findet aktive Gewinnspiele im Internet.

**Quellen:**
- Dedizierte Gewinnspiel-Portale (z.B. gewinnspiele.de, lotto24.de, sweepstakeslovers.com)
- Social Media (Twitter/X, Instagram, Facebook via öffentliche APIs)
- RSS-Feeds von Gewinnspiel-Blogs
- Google-Suche mit definierten Suchbegriffen

**Technologie:**
- Python + Playwright (für JavaScript-lastige Seiten)
- BeautifulSoup / httpx (für statische Seiten)
- Claude AI API (zur Bewertung: Ist das wirklich ein Gewinnspiel? Ist es seriös?)

**Ausgabe pro Gewinnspiel:**
```json
{
  "id": "uuid",
  "url": "https://...",
  "title": "Gewinne einen Tesla",
  "deadline": "2026-07-31",
  "prize": "Tesla Model 3",
  "estimated_value": 45000,
  "participation_type": "form|social|email",
  "trust_score": 0.85,
  "requirements": ["name", "email", "age_18+"],
  "status": "found|queued|participating|done|won|lost"
}
```

**Seriosität-Checks:**
- Domain-Alter prüfen (WHOIS)
- SSL-Zertifikat vorhanden?
- Impressum vorhanden?
- Keine Zahlungsanforderung?
- Claude AI bewertet den Text auf Seriösität

---

### 2. Participant Service

**Aufgabe:** Nimmt automatisch an gefundenen Gewinnspielen teil.

**Technologie:**
- Playwright (Browser-Automatisierung, Headless Chromium)
- 2captcha / AntiCaptcha API (CAPTCHA-Lösung)
- Faker / eigenes Profil-Management (Formulardaten)

**Profil-Verwaltung:**
```yaml
profile:
  first_name: Max
  last_name: Mustermann
  email: gewinnspiele@eigene-domain.de
  birth_date: 1990-01-15
  address:
    street: Musterstraße 1
    city: Berlin
    zip: 10115
    country: DE
  phone: "+49 30 12345678"
```

**Teilnahme-Typen:**
| Typ | Methode |
|-----|---------|
| Web-Formular | Playwright füllt Felder aus |
| E-Mail-Teilnahme | SMTP sendet Teilnahme-E-Mail |
| Social Media | API-Aufruf (Like, Kommentar, Retweet) |
| Newsletter-Abo | Automatisches Abonnieren + Bestätigen |

**Sicherheitsmechanismen:**
- Rate Limiting: Max. N Teilnahmen pro Stunde/Tag
- Blacklist für unseriöse Domains
- Keine Zahlungsdaten eingeben (hardcoded Sperre)
- User-Agent Rotation
- Optional: Proxy-Rotation

---

### 3. Email Manager Service

**Aufgabe:** Verwaltet ein dediziertes E-Mail-Postfach für Gewinnspiele.

**Empfehlung:** Separates E-Mail-Konto nur für Gewinnspiele (z.B. over eigene Domain oder Gmail-Alias).

**Funktionen:**
- IMAP-Verbindung zum Postfach
- Eingehende E-Mails klassifizieren:
  - `WIN_NOTIFICATION` – Gewinnbenachrichtigung
  - `CONFIRMATION` – Teilnahmebestätigung
  - `NEWSLETTER` – Gewinnspiel-Newsletter
  - `SPAM` – Unerwünschte Werbung
- Gewinn-Erkennung via Claude AI (NLP-Analyse des E-Mail-Textes)
- Automatisches Archivieren/Löschen von Spam
- Newsletter-Abbestellung nach Gewinnspiel-Ende

**Gewinn-Erkennungs-Prompt (Claude):**
```
Analysiere diese E-Mail. Handelt es sich um eine Gewinnbenachrichtigung?
Falls ja, extrahiere: Gewinn, Wert, Handlungsbedarf, Frist.
```

---

### 4. Notifier Service

**Aufgabe:** Benachrichtigt den Nutzer bei Gewinnen oder wichtigen Ereignissen.

**Kanäle:**
- **Telegram Bot** (empfohlen – sofortige Push-Benachrichtigung)
- **E-Mail** an persönliches Konto
- **Web Push** über Dashboard
- **Webhook** (für eigene Integrationen)

**Nachrichtentypen:**
```
🎉 GEWINN ERKANNT!
Gewinnspiel: "Gewinne einen Tesla"
Gewinn: Tesla Model 3 (~45.000 €)
Nächster Schritt: Antwort auf E-Mail bis 15.07.2026
E-Mail: von@absender.de

→ [Zur E-Mail] [Zum Gewinnspiel] [Ignorieren]
```

---

### 5. Scheduler Service

**Aufgabe:** Koordiniert alle zeitgesteuerten Aufgaben.

**Cron-Jobs:**
| Job | Intervall | Beschreibung |
|-----|-----------|--------------|
| `scrape_sources` | alle 6h | Neue Gewinnspiele suchen |
| `process_queue` | alle 30min | Teilnahme-Queue abarbeiten |
| `check_email` | alle 15min | Postfach auf Neuigkeiten prüfen |
| `cleanup` | täglich | Abgelaufene Einträge bereinigen |
| `report` | wöchentlich | Wochen-Zusammenfassung senden |

---

### 6. Dashboard (Web UI)

**Aufgabe:** Zentrale Steuerung und Übersicht.

**Features:**
- Live-Übersicht aller gefundenen/laufenden Gewinnspiele
- Teilnahme-Statistiken (Gewinnquote, Teilnahmen gesamt)
- Profil-Verwaltung (eigene Daten)
- Whitelist/Blacklist für Quellen
- Manuelle Teilnahme anstoßen oder sperren
- E-Mail-Postfach-Ansicht
- Logs und Fehlerprotokolle

**Tech-Stack:**
- Backend: FastAPI (Python)
- Frontend: Next.js + Tailwind CSS
- Reverse Proxy: nginx

---

## Technologie-Stack (Gesamt)

| Komponente | Technologie |
|------------|-------------|
| Containerisierung | Docker + Docker Compose |
| Sprache (Services) | Python 3.12 |
| Browser-Automatisierung | Playwright + Chromium |
| CAPTCHA-Lösung | 2captcha API |
| Datenbank | PostgreSQL 16 |
| Cache / Queue | Redis 7 |
| KI-Analyse | Claude API (claude-sonnet-4-6) |
| E-Mail (IMAP/SMTP) | imapclient + smtplib |
| Benachrichtigung | python-telegram-bot |
| Dashboard Backend | FastAPI + SQLAlchemy |
| Dashboard Frontend | Next.js 15 + Tailwind |
| Proxy (optional) | nginx |
| Secrets Management | Docker Secrets / .env |

---

## Datenbankschema (vereinfacht)

```sql
-- Gefundene Gewinnspiele
contests (
  id UUID PRIMARY KEY,
  url TEXT UNIQUE,
  title TEXT,
  source TEXT,
  prize_description TEXT,
  estimated_value NUMERIC,
  deadline TIMESTAMPTZ,
  participation_type TEXT,
  trust_score FLOAT,
  status TEXT,          -- found | queued | participating | done | won | lost
  found_at TIMESTAMPTZ,
  participated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Teilnahme-Protokoll
participations (
  id UUID PRIMARY KEY,
  contest_id UUID REFERENCES contests,
  profile_id UUID REFERENCES profiles,
  method TEXT,
  success BOOLEAN,
  error_message TEXT,
  screenshot_path TEXT,
  participated_at TIMESTAMPTZ DEFAULT NOW()
)

-- Nutzer-Profile für Formulare
profiles (
  id UUID PRIMARY KEY,
  name TEXT,
  email TEXT,
  birth_date DATE,
  address JSONB,
  phone TEXT,
  active BOOLEAN DEFAULT true
)

-- E-Mail-Einträge
emails (
  id UUID PRIMARY KEY,
  contest_id UUID REFERENCES contests,
  message_id TEXT,
  subject TEXT,
  sender TEXT,
  classification TEXT,   -- WIN_NOTIFICATION | CONFIRMATION | NEWSLETTER | SPAM
  win_value NUMERIC,
  action_required TEXT,
  action_deadline TIMESTAMPTZ,
  raw_body TEXT,
  received_at TIMESTAMPTZ
)
```

---

## Sicherheit & Rechtliches

### Technische Sicherheit
- Alle Credentials in `.env` / Docker Secrets (nie im Code)
- Kein Speichern von Kreditkarten- oder Bankdaten
- Rate Limiting verhindert Blocking durch Webseiten
- Automatischer Stop bei Fehlern > Schwellenwert

### Rechtliche Hinweise
- Nur an Gewinnspielen teilnehmen, bei denen **eine Teilnahme pro Person** erlaubt ist
- Teilnahmebedingungen werden von Claude AI geprüft
- Kein Multi-Account-Betrug
- DSGVO: Eigene Daten, kein Missbrauch fremder Identitäten
- Robots.txt respektieren (konfigurierbar)

---

## Projektstruktur

```
winnings/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── docs/
│   └── KONZEPT.md
├── services/
│   ├── scraper/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── sources/       # Gewinnspiel-Quellen
│   │       └── analyzer.py    # Claude AI Bewertung
│   ├── participant/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── browser.py     # Playwright-Steuerung
│   │       └── captcha.py     # CAPTCHA-Handling
│   ├── email-manager/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── imap_client.py
│   │       └── classifier.py  # Claude AI Klassifizierung
│   ├── notifier/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── telegram.py
│   │       └── webhook.py
│   ├── scheduler/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── main.py        # APScheduler
│   └── dashboard/
│       ├── backend/
│       │   ├── Dockerfile
│       │   ├── requirements.txt
│       │   └── src/
│       │       └── main.py    # FastAPI
│       └── frontend/
│           ├── Dockerfile
│           ├── package.json
│           └── src/
├── infrastructure/
│   ├── postgres/
│   │   └── init.sql
│   ├── redis/
│   │   └── redis.conf
│   └── nginx/
│       └── nginx.conf
└── shared/
    └── models.py              # Gemeinsame Datenmodelle
```

---

## Entwicklungs-Phasen

### Phase 1 – Fundament (Woche 1–2)
- [ ] Docker Compose Setup (DB, Redis, nginx)
- [ ] Datenbankschema + Migrationen
- [ ] Shared Models
- [ ] Grundstruktur aller Services

### Phase 2 – Scraper (Woche 3–4)
- [ ] 3–5 Gewinnspiel-Quellen implementieren
- [ ] Claude AI Integration (Seriosität-Prüfung)
- [ ] Queue-System (Redis)

### Phase 3 – Teilnahme (Woche 5–7)
- [ ] Playwright-Integration
- [ ] Formular-Ausfüllen (einfache Fälle)
- [ ] CAPTCHA-Integration
- [ ] Profil-Management

### Phase 4 – E-Mail (Woche 8–9)
- [ ] IMAP-Client
- [ ] Claude AI Klassifizierung
- [ ] Gewinn-Erkennung

### Phase 5 – Benachrichtigung (Woche 10)
- [ ] Telegram Bot
- [ ] Notification Templates

### Phase 6 – Dashboard (Woche 11–13)
- [ ] FastAPI Backend
- [ ] Next.js Frontend
- [ ] Authentifizierung

### Phase 7 – Hardening (Woche 14)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Fehler-Alerting
- [ ] Dokumentation

---

## Externe APIs & Kosten (geschätzt/Monat)

| Service | Zweck | Kosten |
|---------|-------|--------|
| Claude API | Analyse, Klassifizierung | ~5–15 € |
| 2captcha | CAPTCHA-Lösung | ~2–10 € |
| Telegram Bot | Kostenlos | 0 € |
| Proxy (optional) | IP-Rotation | ~5–20 € |
| **Gesamt** | | **~12–45 €/Monat** |

---

## Nächste Schritte

1. `.env.example` konfigurieren (E-Mail, Telegram, API-Keys)
2. `docker-compose.yml` aufsetzen
3. Mit Phase 1 (Fundament) beginnen
4. Ersten Scraper für eine Quelle implementieren und testen
