import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import db
from app.config import settings
from app.pipeline import process_document

app = FastAPI(title="Agente de gastos")
app.mount("/dashboard", StaticFiles(directory="app/static", html=True), name="dashboard")

EXTENSIONES_ADJUNTO_VALIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic"}


def _validar_api_key(x_api_key: str) -> None:
    if not settings.upload_api_key or x_api_key != settings.upload_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")


def _guardar_adjunto_tarea(tarea_id: int, filename: str, contenido: bytes) -> str:
    carpeta = Path(settings.uploads_dir) / "tareas_auto" / str(tarea_id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{uuid.uuid4().hex}_{filename}"
    ruta.write_bytes(contenido)
    return str(ruta)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    nota_usuario: str | None = Form(default=None),
    x_api_key: str = Header(default=""),
):
    _validar_api_key(x_api_key)

    file_bytes = await file.read()
    documento_id = process_document(
        file_bytes, file.filename, fuente="manual", nota_usuario=nota_usuario
    )
    return {"documento_id": documento_id}


@app.get("/documentos/{documento_id}")
def get_documento(documento_id: int, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)

    documento = db.get_documento(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return documento


@app.get("/config-publica")
def config_publica(x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return {
        "telegram_configurado": bool(
            settings.telegram_bot_token and settings.telegram_allowed_chat_id
        ),
        "email_configurado": bool(settings.imap_user),
        "email_poll_interval_seconds": settings.email_poll_interval_seconds,
        "telegram_poll_interval_seconds": settings.telegram_poll_interval_seconds,
    }


@app.get("/nomina/aumentos")
def get_nomina_aumentos(x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_nomina_aumentos()


@app.get("/documentos")
def listar_documentos(limit: int = 50, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_documentos(limit)


@app.get("/gastos")
def listar_gastos(
    tipo: str | None = None,
    es_recurrente: bool | None = None,
    auto_id: int | None = None,
    categoria: str | None = None,
    limit: int = 200,
    x_api_key: str = Header(default=""),
):
    _validar_api_key(x_api_key)
    return db.list_gastos(tipo, es_recurrente, auto_id, categoria, limit)


@app.get("/nomina")
def listar_nomina(limit: int = 50, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_nomina(limit)


@app.get("/km-diario")
def listar_km_diario(limit: int = 60, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_km_diario(limit)


class TareaAutoCrear(BaseModel):
    descripcion: str
    fecha_limite: str | None = None
    km_limite: int | None = None
    auto_id: int | None = None


class TareaAutoCompletar(BaseModel):
    fecha_completada: str | None = None
    costo: float | None = None
    kilometraje_completado: int | None = None


@app.post("/tareas-auto")
def crear_tarea_auto(tarea: TareaAutoCrear, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    if tarea.fecha_limite is None and tarea.km_limite is None:
        raise HTTPException(
            status_code=422, detail="Debe indicar fecha_limite y/o km_limite"
        )
    tarea_id = db.insert_tarea_auto(
        tarea.descripcion, tarea.fecha_limite, tarea.km_limite, tarea.auto_id
    )
    return {"id": tarea_id}


@app.get("/tareas-auto")
def listar_tareas_auto(
    estado: str | None = None, auto_id: int | None = None, x_api_key: str = Header(default="")
):
    _validar_api_key(x_api_key)
    return db.list_tareas_auto(estado, auto_id)


@app.get("/tareas-auto/{tarea_id}")
def obtener_tarea_auto(tarea_id: int, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    tarea = db.get_tarea_auto(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    tarea["adjuntos"] = db.list_tarea_adjuntos(tarea_id)
    return tarea


@app.post("/tareas-auto/{tarea_id}/completar")
def completar_tarea_auto(
    tarea_id: int, datos: TareaAutoCompletar, x_api_key: str = Header(default="")
):
    _validar_api_key(x_api_key)
    if not db.get_tarea_auto(tarea_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.completar_tarea_auto(
        tarea_id, datos.fecha_completada, datos.costo, datos.kilometraje_completado
    )
    return {"ok": True}


@app.post("/tareas-auto/{tarea_id}/adjuntos")
async def subir_adjunto_tarea(
    tarea_id: int, file: UploadFile = File(...), x_api_key: str = Header(default="")
):
    _validar_api_key(x_api_key)
    if not db.get_tarea_auto(tarea_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if Path(file.filename).suffix.lower() not in EXTENSIONES_ADJUNTO_VALIDAS:
        raise HTTPException(status_code=422, detail="Tipo de archivo no soportado")

    contenido = await file.read()
    ruta = _guardar_adjunto_tarea(tarea_id, file.filename, contenido)
    adjunto_id = db.insert_tarea_adjunto(tarea_id, file.filename, ruta)
    return {"id": adjunto_id}


@app.get("/tareas-auto/{tarea_id}/adjuntos/{adjunto_id}")
def descargar_adjunto_tarea(
    tarea_id: int, adjunto_id: int, x_api_key: str = Header(default="")
):
    _validar_api_key(x_api_key)
    adjunto = db.get_tarea_adjunto(adjunto_id)
    if not adjunto or adjunto["tarea_id"] != tarea_id:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    return FileResponse(adjunto["ruta_archivo"], filename=adjunto["nombre_archivo_original"])


class AutoCrear(BaseModel):
    nombre: str
    marca: str | None = None
    modelo: str | None = None
    anio: int | None = None
    placas: str | None = None
    version: str | None = None
    fecha_compra: str | None = None
    kilometraje_inicial: int | None = None
    consumo_km_l: float | None = None


class AutoActualizar(BaseModel):
    nombre: str | None = None
    marca: str | None = None
    modelo: str | None = None
    anio: int | None = None
    placas: str | None = None
    activo: bool | None = None
    version: str | None = None
    fecha_compra: str | None = None
    kilometraje_inicial: int | None = None
    consumo_km_l: float | None = None


@app.post("/autos")
def crear_auto(auto: AutoCrear, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    if db.find_auto_by_nombre(auto.nombre):
        raise HTTPException(status_code=409, detail="Ya existe un auto con ese nombre")
    auto_id = db.insert_auto(
        auto.nombre,
        auto.marca,
        auto.modelo,
        auto.anio,
        auto.placas,
        auto.version,
        auto.fecha_compra,
        auto.kilometraje_inicial,
        auto.consumo_km_l,
    )
    return {"id": auto_id}


@app.get("/autos")
def listar_autos(activo: bool | None = None, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_autos(activo)


@app.get("/autos/{auto_id}")
def obtener_auto(auto_id: int, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    auto = db.get_auto(auto_id)
    if not auto:
        raise HTTPException(status_code=404, detail="Auto no encontrado")
    return auto


@app.patch("/autos/{auto_id}")
def actualizar_auto(auto_id: int, datos: AutoActualizar, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    if not db.get_auto(auto_id):
        raise HTTPException(status_code=404, detail="Auto no encontrado")
    db.update_auto(
        auto_id,
        datos.nombre,
        datos.marca,
        datos.modelo,
        datos.anio,
        datos.placas,
        datos.activo,
        datos.version,
        datos.fecha_compra,
        datos.kilometraje_inicial,
        datos.consumo_km_l,
    )
    return {"ok": True}


@app.post("/webhooks/km-auto")
async def webhook_km_auto(payload: dict, x_forward_secret: str = Header(default="")):
    if not settings.km_auto_forward_secret or x_forward_secret != settings.km_auto_forward_secret:
        raise HTTPException(status_code=401, detail="Secreto inválido")

    fecha = payload.get("fecha")
    km = payload.get("km")
    vehiculo = payload.get("vehiculo") or "default"
    if fecha is None or km is None:
        raise HTTPException(status_code=422, detail="Faltan campos 'fecha' y/o 'km'")

    db.upsert_km_diario(fecha=fecha, vehiculo=vehiculo, km=km, resumen=payload)
    return {"ok": True}
