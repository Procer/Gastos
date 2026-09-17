import fitz  # PyMuPDF

# Si un PDF tiene menos texto que esto, se asume que es escaneado (imagen sin texto
# seleccionable) y se manda por el camino de OCR en vez de usarse tal cual.
TEXTO_MINIMO_PDF_NATIVO = 30


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def es_pdf_escaneado(texto_extraido: str) -> bool:
    return len(texto_extraido.strip()) < TEXTO_MINIMO_PDF_NATIVO
