from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential

from app.config import settings

# Se usa 'prebuilt-layout' (OCR + orden de lectura + tablas) y no 'prebuilt-receipt':
# el modelo de recibos no tiene soporte confiable para tickets mexicanos y no sirve
# para recibos de nómina. El texto que devuelve aquí siempre pasa después por el LLM,
# que es la única fuente de verdad para estructurar los datos.
MODELO = "prebuilt-layout"


def extract_text_from_image(file_bytes: bytes) -> str:
    client = DocumentIntelligenceClient(
        endpoint=settings.azure_doc_intel_endpoint,
        credential=AzureKeyCredential(settings.azure_doc_intel_key),
    )
    poller = client.begin_analyze_document(
        MODELO, AnalyzeDocumentRequest(bytes_source=file_bytes)
    )
    result = poller.result()
    return result.content or ""
