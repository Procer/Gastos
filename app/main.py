from fastapi import FastAPI, File, Header, HTTPException, UploadFile

from app import db
from app.config import settings
from app.pipeline import process_document

app = FastAPI(title="Agente de gastos")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/upload")
async def upload(file: UploadFile = File(...), x_api_key: str = Header(default="")):
    if not settings.upload_api_key or x_api_key != settings.upload_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    file_bytes = await file.read()
    documento_id = process_document(file_bytes, file.filename, fuente="manual")
    return {"documento_id": documento_id}


@app.get("/documentos/{documento_id}")
def get_documento(documento_id: int, x_api_key: str = Header(default="")):
    if not settings.upload_api_key or x_api_key != settings.upload_api_key:
        raise HTTPException(status_code=401, detail="API key inválida")

    documento = db.get_documento(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return documento
