import fitz  # PyMuPDF

# Resolución razonable para OCR sin generar imágenes enormes.
ZOOM = 2.0


def render_pdf_pages_to_images(file_bytes: bytes) -> list[bytes]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        matrix = fitz.Matrix(ZOOM, ZOOM)
        imagenes = []
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            imagenes.append(pix.tobytes("png"))
        return imagenes
    finally:
        doc.close()
