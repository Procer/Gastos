import re

# Tolerante a variantes: "km:45230", "km 45230", "km=45230", "KM: 45,230".
_KM_REGEX = re.compile(r"km\s*[:=]?\s*([\d,]+)", re.IGNORECASE)

# Identifica a qué auto pertenece el comprobante: "auto:sedan", "auto sedan", "AUTO=Sedan".
# El nombre no lleva espacios (se corta en el primer espacio/coma/salto de línea).
_AUTO_REGEX = re.compile(r"auto\s*[:=]?\s*([^\s,;]+)", re.IGNORECASE)


def parse_kilometraje(nota_usuario: str | None) -> int | None:
    if not nota_usuario:
        return None
    match = _KM_REGEX.search(nota_usuario)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def parse_auto_tag(nota_usuario: str | None) -> str | None:
    if not nota_usuario:
        return None
    match = _AUTO_REGEX.search(nota_usuario)
    if not match:
        return None
    return match.group(1)
