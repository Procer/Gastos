import re

# Tolerante a variantes: "km:45230", "km 45230", "km=45230", "KM: 45,230".
_KM_REGEX = re.compile(r"km\s*[:=]?\s*([\d,]+)", re.IGNORECASE)


def parse_kilometraje(nota_usuario: str | None) -> int | None:
    if not nota_usuario:
        return None
    match = _KM_REGEX.search(nota_usuario)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))
