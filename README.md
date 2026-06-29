# Winnings – Automatisiertes Gewinnspiel-System

Vollautomatisiertes Docker-basiertes System, das im Internet nach Gewinnspielen sucht, automatisch teilnimmt und dich per Telegram/E-Mail benachrichtigt, wenn du gewonnen hast.

## Schnellstart

```bash
# 1. Konfiguration
cp .env.example .env
# .env mit deinen Daten befüllen (E-Mail, Telegram, API-Keys)

# 2. Starten
docker compose up -d

# 3. Dashboard öffnen
open http://localhost:8080
```

## Architektur

| Service | Aufgabe |
|---------|---------|
| `scraper` | Sucht Gewinnspiele auf Portalen und RSS-Feeds, bewertet Seriösität via Claude AI |
| `participant` | Füllt Formulare aus und nimmt teil (Playwright + CAPTCHA-Lösung) |
| `email-manager` | Überwacht IMAP-Postfach, erkennt Gewinne via Claude AI |
| `notifier` | Sendet Telegram/E-Mail-Benachrichtigungen bei Gewinnen |
| `scheduler` | Koordiniert alle Cron-Jobs |
| `dashboard` | Web-UI + REST-API für Übersicht und Konfiguration |

## Voraussetzungen

- Docker + Docker Compose
- Anthropic API Key ([console.anthropic.com](https://console.anthropic.com))
- Dediziertes E-Mail-Konto für Gewinnspiele (empfohlen: Gmail mit App-Passwort)
- Telegram Bot Token (optional, für Push-Benachrichtigungen)
- 2captcha API Key (optional, für CAPTCHA-Lösung)

## Konfiguration (.env)

Alle wichtigen Einstellungen in `.env.example` dokumentiert. Mindestanforderungen:

```env
ANTHROPIC_API_KEY=sk-ant-...
EMAIL_ADDRESS=gewinnspiele@gmail.com
EMAIL_PASSWORD=app-passwort
POSTGRES_PASSWORD=sicheres-passwort
DASHBOARD_SECRET_KEY=zufaelliger-schluessel
```

## Kosten (geschätzt)

| Komponente | Monatlich |
|------------|-----------|
| Claude API | ~5–15 € |
| 2captcha (optional) | ~2–10 € |
| Proxy (optional) | ~5–20 € |
| **Gesamt** | **~12–45 €** |

## Rechtliches

- Nur an Gewinnspielen mit freier Teilnahme teilnehmen (keine Zahlung erforderlich)
- Pro Gewinnspiel nur eine Teilnahme (Teilnahmebedingungen werden geprüft)
- Robots.txt wird respektiert (konfigurierbar)
- Eigene persönliche Daten – kein Identitätsmissbrauch

## Entwicklung

Detailliertes Konzept: [docs/KONZEPT.md](docs/KONZEPT.md)

```bash
# Nur Infrastruktur starten (DB + Redis)
docker compose up postgres redis -d

# Einzelnen Service neu bauen
docker compose build scraper && docker compose up scraper -d

# Logs verfolgen
docker compose logs -f scraper participant email-manager
```
