import smtplib
from email.mime.text import MIMEText

from app.config import settings


def send_error_alert(documento_id: int, filename: str, mensaje_error: str) -> None:
    if not settings.smtp_user or not settings.alert_email_to:
        return

    cuerpo = (
        f"Falló el procesamiento de un comprobante.\n\n"
        f"Documento ID: {documento_id}\n"
        f"Archivo: {filename}\n"
        f"Error: {mensaje_error}\n"
    )
    mensaje = MIMEText(cuerpo, "plain", "utf-8")
    mensaje["Subject"] = f"[Agente de gastos] Error procesando documento #{documento_id}"
    mensaje["From"] = settings.smtp_user
    mensaje["To"] = settings.alert_email_to

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_app_password)
        server.sendmail(settings.smtp_user, [settings.alert_email_to], mensaje.as_string())
