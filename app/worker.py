import logging
import threading
import time

from app.config import settings
from app.ingestion.email_ingest import check_inbox
from app.ingestion.telegram_ingest import check_telegram

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# httpx registra la URL completa de cada request en INFO, y las llamadas a Telegram
# llevan el bot token en la URL — se sube a WARNING para no filtrar el token en logs.
logging.getLogger("httpx").setLevel(logging.WARNING)


def _loop_email() -> None:
    logger.info(
        "Worker de correo iniciado (revisa cada %s segundos)",
        settings.email_poll_interval_seconds,
    )
    while True:
        try:
            check_inbox()
        except Exception:
            logger.exception("Error revisando el correo, se reintenta en el siguiente ciclo")
        time.sleep(settings.email_poll_interval_seconds)


def _loop_telegram() -> None:
    if not settings.telegram_bot_token:
        logger.info("TELEGRAM_BOT_TOKEN no configurado, no se revisa Telegram")
        return
    logger.info("Worker de Telegram iniciado (long polling)")
    while True:
        try:
            check_telegram()
        except Exception:
            logger.exception("Error revisando Telegram, se reintenta en el siguiente ciclo")
        time.sleep(settings.telegram_poll_interval_seconds)


def main() -> None:
    threading.Thread(target=_loop_telegram, daemon=True).start()
    _loop_email()


if __name__ == "__main__":
    main()
