from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from app import db
from app.config import settings
from app.pipeline import process_document

app = FastAPI(title="Agente de gastos")


def _validar_api_key(x_api_key: str) -> None:
    if not settings.upload_api_key or x_api_key != settings.upload_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")


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


@app.get("/nomina/aumentos")
def get_nomina_aumentos(x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_nomina_aumentos()


class TareaAutoCrear(BaseModel):
    descripcion: str
    fecha_limite: str | None = None
    km_limite: int | None = None


@app.post("/tareas-auto")
def crear_tarea_auto(tarea: TareaAutoCrear, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    if tarea.fecha_limite is None and tarea.km_limite is None:
        raise HTTPException(
            status_code=422, detail="Debe indicar fecha_limite y/o km_limite"
        )
    tarea_id = db.insert_tarea_auto(tarea.descripcion, tarea.fecha_limite, tarea.km_limite)
    return {"id": tarea_id}


@app.get("/tareas-auto")
def listar_tareas_auto(estado: str | None = None, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    return db.list_tareas_auto(estado)


@app.get("/tareas-auto/{tarea_id}")
def obtener_tarea_auto(tarea_id: int, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    tarea = db.get_tarea_auto(tarea_id)
    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return tarea


@app.post("/tareas-auto/{tarea_id}/completar")
def completar_tarea_auto(tarea_id: int, x_api_key: str = Header(default="")):
    _validar_api_key(x_api_key)
    if not db.get_tarea_auto(tarea_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.completar_tarea_auto(tarea_id)
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
