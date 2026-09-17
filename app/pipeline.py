import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

from app import db
from app.alerts.email_alert import send_error_alert
from app.classification.llm_classifier import classify_document
from app.config import settings
from app.extraction.pdf_extractor import es_pdf_escaneado, extract_text_from_pdf
from app.extraction.pdf_to_images import render_pdf_pages_to_images
from app.extraction.image_ocr import extract_text_from_image
from app.km_parser import parse_auto_tag, parse_kilometraje

logger = logging.getLogger(__name__)

EXTENSIONES_PDF = {".pdf"}
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _detectar_tipo_archivo(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in EXTENSIONES_PDF:
        return "pdf"
    if ext in EXTENSIONES_IMAGEN:
        return "imagen"
    raise ValueError(f"Extensión de archivo no soportada: {ext}")


def _guardar_archivo(file_bytes: bytes, filename: str) -> str:
    hoy = datetime.utcnow()
    carpeta = Path(settings.uploads_dir) / f"{hoy:%Y}" / f"{hoy:%m}"
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre_unico = f"{uuid.uuid4().hex}_{filename}"
    ruta = carpeta / nombre_unico
    ruta.write_bytes(file_bytes)
    return str(ruta)


def _extraer_texto(file_bytes: bytes, tipo_archivo: str) -> str:
    if tipo_archivo == "imagen":
        return extract_text_from_image(file_bytes)

    texto = extract_text_from_pdf(file_bytes)
    if not es_pdf_escaneado(texto):
        return texto

    # PDF escaneado: no tiene texto nativo, se renderiza cada página a imagen y se
    # manda por el mismo camino de OCR que las fotos.
    paginas = render_pdf_pages_to_images(file_bytes)
    return "\n".join(extract_text_from_image(pagina) for pagina in paginas)


def _resolver_auto_id(nota_usuario: str | None) -> int | None:
    """Decide a qué auto pertenece un gasto de tipo 'auto'.

    Si la nota trae "auto:nombre" y coincide con un auto registrado, se usa ese.
    Si no trae tag pero solo hay un auto activo registrado, se asume que es ese
    (no hay ambigüedad posible). En cualquier otro caso queda sin asignar.
    """
    tag = parse_auto_tag(nota_usuario)
    if tag:
        auto = db.find_auto_by_nombre(tag)
        return auto["id"] if auto else None

    unico = db.get_unico_auto_activo()
    return unico["id"] if unico else None


def _registrar_aumento_nomina(nomina_id: int, nomina) -> None:
    """Compara el sueldo_base contra el recibo anterior del mismo empleador.

    Corre en su propio try/except *después* de que el documento ya quedó como
    completado — si esta comparación falla, nunca debe tumbar el documento a error.
    """
    if not nomina.empleador or nomina.sueldo_base is None:
        return  # sin empleador o sin sueldo_base no se puede comparar con seguridad

    sueldo_anterior = db.find_sueldo_base_anterior(nomina.empleador, nomina_id)
    if sueldo_anterior is None:
        return  # primer recibo de este empleador, no es un "aumento" falso

    if abs(nomina.sueldo_base - sueldo_anterior) > 0.01:
        db.insert_nomina_aumento(
            nomina_id=nomina_id,
            empleador=nomina.empleador,
            sueldo_base_anterior=sueldo_anterior,
            sueldo_base_nuevo=nomina.sueldo_base,
            fecha_pago=nomina.fecha_pago,
        )


def process_document(
    file_bytes: bytes,
    filename: str,
    fuente: str,
    referencia_fuente: str | None = None,
    nota_usuario: str | None = None,
) -> int:
    """Procesa un comprobante venga de donde venga (subida manual, correo o Telegram).

    Devuelve el id de la fila en `documentos`. Nunca lanza excepción hacia afuera:
    cualquier fallo se registra como estado='error' y se notifica por correo.
    """
    hash_archivo = hashlib.sha256(file_bytes).hexdigest()

    existente = db.find_documento_by_hash(hash_archivo)
    if existente:
        logger.info("Documento duplicado (hash=%s), no se reprocesa", hash_archivo)
        return existente["id"]

    tipo_archivo = _detectar_tipo_archivo(filename)
    ruta_archivo = _guardar_archivo(file_bytes, filename)
    kilometraje = parse_kilometraje(nota_usuario)

    documento_id = db.insert_documento(
        fuente=fuente,
        referencia_fuente=referencia_fuente,
        hash_archivo=hash_archivo,
        nombre_archivo_original=filename,
        ruta_archivo=ruta_archivo,
        tipo_archivo=tipo_archivo,
        nota_usuario=nota_usuario,
    )

    try:
        texto = _extraer_texto(file_bytes, tipo_archivo)
        db.update_documento_texto(documento_id, texto)

        resultado = classify_document(texto)

        gasto_id = None
        nomina_id = None
        if resultado.gasto is not None:
            resultado.gasto.kilometraje = kilometraje
            if resultado.gasto.tipo == "auto":
                resultado.gasto.auto_id = _resolver_auto_id(nota_usuario)
            gasto_id = db.insert_gasto(documento_id, resultado.gasto)
        if resultado.nomina is not None:
            nomina_id = db.insert_nomina(documento_id, resultado.nomina)

        db.marcar_documento_completado(
            documento_id=documento_id,
            tipo_documento=resultado.tipo_documento,
            respuesta_llm_json=resultado.respuesta_cruda,
            gasto_id=gasto_id,
            nomina_id=nomina_id,
        )

        if nomina_id is not None:
            try:
                _registrar_aumento_nomina(nomina_id, resultado.nomina)
            except Exception:
                logger.exception(
                    "Falló la comparación de aumento de nómina para documento %s", documento_id
                )
    except Exception as exc:
        logger.exception("Error procesando documento %s", documento_id)
        db.marcar_documento_error(documento_id, str(exc))
        try:
            send_error_alert(documento_id, filename, str(exc))
            db.marcar_alerta_enviada(documento_id)
        except Exception:
            logger.exception("Falló el envío de la alerta de error para documento %s", documento_id)

    return documento_id
