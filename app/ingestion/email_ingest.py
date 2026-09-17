import email
import imaplib
import logging
from email.header import decode_header
from email.message import Message
from pathlib import Path

from app.config import settings
from app.pipeline import process_document

logger = logging.getLogger(__name__)

EXTENSIONES_VALIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _tiene_extension_valida(filename: str) -> bool:
    return Path(filename).suffix.lower() in EXTENSIONES_VALIDAS


def _decodificar_asunto(msg: Message) -> str | None:
    asunto_crudo = msg.get("Subject")
    if not asunto_crudo:
        return None
    partes = decode_header(asunto_crudo)
    return "".join(
        texto.decode(codificacion or "utf-8", errors="replace") if isinstance(texto, bytes) else texto
        for texto, codificacion in partes
    )


def _procesar_adjuntos(msg: Message, referencia_fuente: str) -> None:
    nota_usuario = _decodificar_asunto(msg)
    for part in msg.walk():
        filename = part.get_filename()
        if not filename or not _tiene_extension_valida(filename):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        process_document(
            payload,
            filename,
            fuente="email",
            referencia_fuente=referencia_fuente,
            nota_usuario=nota_usuario,
        )


def check_inbox() -> None:
    """Revisa correos no leídos, procesa sus adjuntos (PDF/imagen) y los marca como leídos."""
    conn = imaplib.IMAP4_SSL(settings.imap_host)
    try:
        conn.login(settings.imap_user, settings.imap_app_password)
        conn.select("INBOX")
        _, data = conn.search(None, "UNSEEN")
        message_ids = data[0].split()
        for msg_id in message_ids:
            _, msg_data = conn.fetch(msg_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            referencia_fuente = msg.get("Message-ID") or f"sin-message-id-{msg_id.decode()}"
            try:
                _procesar_adjuntos(msg, referencia_fuente)
            except Exception:
                logger.exception("Error procesando adjuntos del correo %s", referencia_fuente)
            conn.store(msg_id, "+FLAGS", "\\Seen")
    finally:
        conn.logout()
