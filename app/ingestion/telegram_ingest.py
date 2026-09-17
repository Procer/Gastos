import logging
from pathlib import Path

import httpx

from app.config import settings
from app.pipeline import process_document

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
EXTENSIONES_VALIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}

# Offset de Telegram: solo se mantiene en memoria durante la vida del proceso.
# No hace falta persistirlo entre reinicios porque el pipeline ya deduplica por
# hash del archivo (ver app/pipeline.py) — si Telegram reenvía un mensaje viejo
# tras un reinicio, el archivo repetido simplemente no se reprocesa.
_offset = 0


def _descargar_archivo(file_id: str, client: httpx.Client) -> bytes:
    info = client.get(
        f"{API_BASE}/bot{settings.telegram_bot_token}/getFile",
        params={"file_id": file_id},
    ).json()
    file_path = info["result"]["file_path"]
    resp = client.get(f"{API_BASE}/file/bot{settings.telegram_bot_token}/{file_path}")
    return resp.content


def _extraer_adjunto(message: dict, client: httpx.Client) -> tuple[bytes, str] | None:
    documento = message.get("document")
    if documento:
        file_id = documento["file_id"]
        filename = documento.get("file_name") or f"{file_id}.pdf"
        if Path(filename).suffix.lower() not in EXTENSIONES_VALIDAS:
            return None
        return _descargar_archivo(file_id, client), filename

    fotos = message.get("photo")
    if fotos:
        # Telegram manda la misma foto en varias resoluciones; la última es la de mayor calidad.
        file_id = fotos[-1]["file_id"]
        return _descargar_archivo(file_id, client), f"{file_id}.jpg"

    return None


def check_telegram() -> None:
    global _offset

    if not settings.telegram_bot_token:
        return

    with httpx.Client(timeout=35) as client:
        resp = client.get(
            f"{API_BASE}/bot{settings.telegram_bot_token}/getUpdates",
            params={"offset": _offset, "timeout": 30},
        )
        data = resp.json()

        for update in data.get("result", []):
            _offset = update["update_id"] + 1
            message = update.get("message")
            if not message:
                continue

            chat_id = str(message.get("chat", {}).get("id", ""))
            if not settings.telegram_allowed_chat_id:
                logger.warning(
                    "TELEGRAM_ALLOWED_CHAT_ID no configurado, se ignoran mensajes de Telegram"
                )
                continue
            if chat_id != settings.telegram_allowed_chat_id:
                logger.warning("Mensaje de Telegram ignorado, chat_id no autorizado: %s", chat_id)
                continue

            try:
                adjunto = _extraer_adjunto(message, client)
            except Exception:
                logger.exception(
                    "Error descargando adjunto de Telegram (update_id=%s)", update["update_id"]
                )
                continue

            if not adjunto:
                continue

            file_bytes, filename = adjunto
            process_document(
                file_bytes, filename, fuente="telegram", referencia_fuente=str(update["update_id"])
            )
