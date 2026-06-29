"""Claude AI-basierte Analyse und Seriositätsprüfung von Gewinnspielen."""
import json
import os
from datetime import date

import anthropic

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

ANALYSIS_PROMPT = """\
Du analysierst eine Webseite um zu bestimmen ob es ein aktuell laufendes, seriöses Gewinnspiel ist.
Heute ist: {today}

URL: {url}
Titel: {title}
Seiteninhalt (Auszug):
{content}

Antworte NUR mit einem JSON-Objekt (kein Markdown) mit diesen Feldern:
- is_contest (bool): Handelt es sich um ein echtes Gewinnspiel?
- is_active (bool): Läuft das Gewinnspiel noch? (Deadline nicht abgelaufen, nicht als beendet markiert)
- trust_score (float 0-1): Wie seriös wirkt es? 1 = sehr seriös
- prize_description (str|null): Beschreibung des Gewinns
- estimated_value (float|null): Geschätzter Gewinnwert in Euro
- deadline (str|null): Teilnahmeschluss als ISO-Datum (YYYY-MM-DD) oder null
- participation_type (str): "form", "email", "social" oder "unknown"
- requirements (list[str]): Teilnahmevoraussetzungen (z.B. ["name", "email", "age_18+"])
- skip_reason (str|null): Grund zum Überspringen, PFLICHT wenn is_active=false oder is_contest=false

Wichtig:
- Setze is_active=false wenn: Deadline bereits überschritten, Gewinner schon gezogen, Aktion beendet
- Setze skip_reason wenn Zahlung nötig, Gewinnspiel abgelaufen, oder offensichtlich unseriös

Trust-Score:
- 0.9-1.0: Bekannte seriöse Marke, klare Bedingungen, kein Geld nötig
- 0.7-0.9: Normales Gewinnspiel, Impressum vorhanden
- 0.5-0.7: Unbekannter Veranstalter, keine offensichtlichen Red Flags
- 0.0-0.5: Verdächtig (Zahlung, übertriebene Gewinne, fehlende Infos)
"""


async def analyze_contest(url: str, title: str, content: str) -> dict:
    """Analysiert eine Seite mit Claude AI auf Gewinnspiel-Seriösität."""
    prompt = ANALYSIS_PROMPT.format(
        today=date.today().isoformat(),
        url=url,
        title=title,
        content=content[:3000],
    )

    message = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return json.loads(raw)


EMAIL_ANALYSIS_PROMPT = """\
Analysiere diese E-Mail und bestimme ob es eine Gewinnbenachrichtigung ist.

Betreff: {subject}
Absender: {sender}
Inhalt:
{body}

Antworte NUR mit einem JSON-Objekt:
- is_win_notification (bool): Handelt es sich um eine Gewinnbenachrichtigung?
- classification ("WIN_NOTIFICATION"|"CONFIRMATION"|"NEWSLETTER"|"SPAM"|"UNKNOWN")
- win_description (str|null): Was wurde gewonnen?
- win_value (float|null): Geschätzter Wert in Euro
- action_required (str|null): Was muss der Gewinner tun?
- action_deadline (str|null): Bis wann muss gehandelt werden? (ISO-Datum)
"""


async def classify_email(subject: str, sender: str, body: str) -> dict:
    """Klassifiziert eine E-Mail mit Claude AI."""
    prompt = EMAIL_ANALYSIS_PROMPT.format(
        subject=subject, sender=sender, body=body[:2000]
    )

    message = await client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    return json.loads(raw)
