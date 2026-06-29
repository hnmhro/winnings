"""Playwright-basierte Formular-Ausfüllung für Gewinnspiele."""
import logging
from typing import Callable

from playwright.async_api import Page

logger = logging.getLogger("participant.browser")

FIELD_PATTERNS = {
    "first_name": ["vorname", "first_name", "firstname", "fname", "givenname"],
    "last_name": ["nachname", "last_name", "lastname", "lname", "familyname", "surname"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["telefon", "phone", "tel", "mobile", "handy"],
    "zip": ["plz", "postleitzahl", "zip", "postal"],
    "city": ["ort", "stadt", "city", "town"],
    "street": ["straße", "strasse", "street", "address"],
    "birth_date": ["geburtsdatum", "birthday", "birth_date", "dob"],
}


async def find_and_fill_field(page: Page, field_key: str, value: str) -> bool:
    """Sucht ein Formularfeld anhand bekannter Muster und füllt es aus."""
    patterns = FIELD_PATTERNS.get(field_key, [field_key])
    for pattern in patterns:
        selectors = [
            f"input[name*='{pattern}']",
            f"input[id*='{pattern}']",
            f"input[placeholder*='{pattern}']",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(value)
                    return True
            except Exception:
                continue
    return False


async def accept_privacy_checkbox(page: Page) -> None:
    """Akzeptiert Datenschutz-Checkboxen falls vorhanden."""
    privacy_selectors = [
        "input[type='checkbox'][name*='datenschutz']",
        "input[type='checkbox'][name*='privacy']",
        "input[type='checkbox'][name*='agb']",
        "input[type='checkbox'][name*='terms']",
        "input[type='checkbox'][id*='datenschutz']",
        "input[type='checkbox'][id*='privacy']",
    ]
    for sel in privacy_selectors:
        try:
            el = page.locator(sel).first
            if await el.count() > 0 and not await el.is_checked():
                await el.check()
        except Exception:
            pass


async def fill_contest_form(
    page: Page,
    url: str,
    profile: dict,
    captcha_solver: Callable | None = None,
) -> bool:
    """Füllt ein Gewinnspiel-Formular aus und sendet es ab."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        filled_count = 0
        for field_key, value in profile.items():
            if value and await find_and_fill_field(page, field_key, str(value)):
                filled_count += 1

        if filled_count == 0:
            logger.warning("Keine Felder gefunden auf %s", url)
            return False

        await accept_privacy_checkbox(page)

        if captcha_solver:
            captcha_solved = await captcha_solver(page, url)
            if not captcha_solved:
                logger.warning("CAPTCHA nicht lösbar: %s", url)
                return False

        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Teilnehmen')",
            "button:has-text('Jetzt teilnehmen')",
            "button:has-text('Absenden')",
            "button:has-text('Submit')",
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    logger.info("Formular abgesendet: %s", url)
                    return True
            except Exception:
                continue

        logger.warning("Kein Submit-Button gefunden: %s", url)
        return False

    except Exception as exc:
        logger.error("Browser-Fehler bei %s: %s", url, exc)
        return False
