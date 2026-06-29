"""CAPTCHA-Lösung via 2captcha."""
import logging
import os

from playwright.async_api import Page

logger = logging.getLogger("participant.captcha")

API_KEY = os.getenv("TWOCAPTCHA_API_KEY")


async def solve_captcha(page: Page, url: str) -> bool:
    """Erkennt und löst reCAPTCHA v2 via 2captcha-Service."""
    if not API_KEY:
        logger.debug("Kein CAPTCHA-API-Key konfiguriert, überspringe.")
        return True

    try:
        sitekey_el = page.locator(".g-recaptcha[data-sitekey]").first
        if await sitekey_el.count() == 0:
            return True

        sitekey = await sitekey_el.get_attribute("data-sitekey")
        if not sitekey:
            return True

        logger.info("reCAPTCHA erkannt, löse via 2captcha...")
        from twocaptcha import TwoCaptcha  # type: ignore
        solver = TwoCaptcha(API_KEY)
        result = solver.recaptcha(sitekey=sitekey, url=url)
        token = result["code"]

        await page.evaluate(
            f"document.getElementById('g-recaptcha-response').value = '{token}'"
        )
        logger.info("CAPTCHA gelöst.")
        return True

    except Exception as exc:
        logger.warning("CAPTCHA-Lösung fehlgeschlagen: %s", exc)
        return False
