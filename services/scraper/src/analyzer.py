"""Claude AI-basierte Analyse und Seriositätsprüfung von Gewinnspielen."""
import json
import os
import re
from datetime import date

import anthropic

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

ANALYSIS_PROMPT = """\
Du analysierst einen Gewinnspiel-Hinweis um zu bestimmen ob er aktuell und seriös ist.
Heute ist: {today}

URL: {url}
Titel: {title}
Seiteninhalt (kann leer sein falls nicht abrufbar):
{content}

Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Text davor/danach) mit diesen Feldern:
- is_contest (bool): Handelt es sich um ein echtes Gewinnspiel?
- is_active (bool): Läuft das Gewinnspiel noch? (Deadline nicht abgelaufen, nicht beendet)
- trust_score (float 0-1): Wie seriös wirkt es?
- prize_description (str|null): Beschreibung des Gewinns
- estimated_value (float|null): Geschätzter Gewinnwert in Euro
- deadline (str|null): Teilnahmeschluss als ISO-Datum (YYYY-MM-DD) oder null
- participation_type (str): "form", "email", "social" oder "unknown"
- requirements (list[str]): Teilnahmevoraussetzungen
- skip_reason (str|null): Pflicht wenn is_active=false oder is_contest=false

Hinweis: Wenn kein Seiteninhalt vorhanden, analysiere nur anhand von Titel und URL.
Trust-Score: 0.9+ bekannte Marke, 0.7-0.9 normal, 0.5-0.7 unbekannt, <0.5 verdächtig.
"""

EMAIL_ANALYSIS_PROMPT = """\
Analysiere diese E-Mail und bestimme ob es eine Gewinnbenachrichtigung ist.

Betreff: {subject}
Absender: {sender}
Inhalt:
{body}

Antworte NUR mit einem JSON-Objekt (kein Markdown):
- is_win_notification (bool)
- classification ("WIN_NOTIFICATION"|"CONFIRMATION"|"NEWSLETTER"|"SPAM"|"UNKNOWN")
- win_description (str|null)
- win_value (float|null): Geschätzter Wert in Euro
- action_required (str|null)
- action_deadline (str|null): ISO-Datum oder null
"""


def _parse_json(raw: str) -> dict:
    """Parst JSON aus Claude-Antwort, toleriert Markdown-Blöcke und Präambeln."""
    raw = raw.strip()
    if not raw:
        return {"is_contest": False, "skip_reason": "Leere AI-Antwort"}

    # Direkt parsen
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # JSON aus Markdown-Codeblock extrahieren
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Erstes JSON-Objekt im Text suchen
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"is_contest": False, "skip_reason": f"Ungültiges JSON: {raw[:100]}"}


async def analyze_contest(url: str, title: str, content: str) -> dict:
    """Analysiert eine Seite mit Claude AI auf Gewinnspiel-Seriösität."""
    prompt = ANALYSIS_PROMPT.format(
        today=date.today().isoformat(),
        url=url,
        title=title,
        content=content[:3000] if content else "(nicht abrufbar)",
    )
    message = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(message.content[0].text)


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
    return _parse_json(message.content[0].text)
