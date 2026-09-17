import json
from typing import Any

import anthropic

from app.config import settings
from app.models import (
    CATEGORIAS_AUTO,
    CATEGORIAS_PERSONAL,
    ClasificacionResultado,
    GastoData,
    NominaData,
)

SYSTEM_PROMPT = f"""Eres un asistente que clasifica comprobantes financieros en español (México).
Vas a recibir el texto crudo extraído de un comprobante (ticket, factura o recibo de nómina).

Debes decidir el tipo de documento:
- "gasto_personal": cualquier gasto que NO sea del auto (comida, salud, entretenimiento, compras, servicios, transporte, etc.)
- "gasto_auto": cualquier gasto relacionado al auto (gasolina, mantenimiento, seguro, verificación, tenencia, refacciones, casetas/estacionamiento, multas, etc.)
- "recibo_nomina": un recibo de nómina o sueldo (tiene percepciones, deducciones, neto a pagar, periodo de pago)

Categorías válidas para gasto_auto: {sorted(CATEGORIAS_AUTO)}
Categorías válidas para gasto_personal: {sorted(CATEGORIAS_PERSONAL)}

Llama siempre a la herramienta "registrar_documento" con los datos que puedas extraer del texto.
Si un dato no aparece en el texto, usa null. Los montos son números (no strings), las fechas en formato YYYY-MM-DD.
Solo llena el objeto "gasto" si tipo_documento es gasto_personal o gasto_auto. Solo llena "nomina" si tipo_documento es recibo_nomina.

Para gastos, decide también "es_recurrente": true si es un gasto fijo que se repite periódicamente
(renta, suscripciones, seguros anuales, servicios como luz/agua/internet/teléfono), false si es un
gasto variable puntual (comida, gasolina, compras, entretenimiento, transporte ocasional).

Para recibos de nómina, extrae también "sueldo_base": el sueldo base/tabulador del periodo, es decir
el concepto de percepción fijo (a veces llamado "sueldo", "sueldo base", "salario base" o similar),
SIN incluir bonos, horas extra, aguinaldo ni otras percepciones variables. Si no puedes identificarlo
con certeza en el detalle de percepciones, usa null.
"""

# Gemini no recibe la herramienta como tool-calling con schema estricto en este flujo;
# se le pide directamente que devuelva ese mismo JSON, así que se le describe la forma
# exacta esperada en el propio prompt.
GEMINI_JSON_SHAPE = """
Responde ÚNICAMENTE con un JSON (sin texto adicional, sin markdown) con esta forma exacta:
{
  "tipo_documento": "gasto_personal" | "gasto_auto" | "recibo_nomina",
  "gasto": null o {
    "tipo": "personal" | "auto",
    "categoria": "...",
    "monto": 123.45,
    "moneda": "MXN",
    "fecha": "YYYY-MM-DD",
    "comercio": "..." o null,
    "descripcion": "..." o null,
    "metodo_pago": "..." o null,
    "es_recurrente": true o false
  },
  "nomina": null o {
    "empleador": "..." o null,
    "periodo_inicio": "YYYY-MM-DD" o null,
    "periodo_fin": "YYYY-MM-DD" o null,
    "fecha_pago": "YYYY-MM-DD" o null,
    "percepciones": 123.45,
    "deducciones": 123.45,
    "neto_pagado": 123.45,
    "sueldo_base": 123.45 o null,
    "detalle_percepciones": [{"concepto": "...", "monto": 123.45}],
    "detalle_deducciones": [{"concepto": "...", "monto": 123.45}],
    "moneda": "MXN"
  }
}
Llena "gasto" solo si tipo_documento es gasto_personal o gasto_auto (deja "nomina" en null).
Llena "nomina" solo si tipo_documento es recibo_nomina (deja "gasto" en null).
"""

TOOL_SCHEMA = {
    "name": "registrar_documento",
    "description": "Registra la clasificación y los datos extraídos de un comprobante.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tipo_documento": {
                "type": "string",
                "enum": ["gasto_personal", "gasto_auto", "recibo_nomina"],
            },
            "gasto": {
                "type": ["object", "null"],
                "properties": {
                    "tipo": {"type": "string", "enum": ["personal", "auto"]},
                    "categoria": {"type": "string"},
                    "monto": {"type": "number"},
                    "moneda": {"type": "string", "default": "MXN"},
                    "fecha": {"type": "string", "description": "YYYY-MM-DD"},
                    "comercio": {"type": ["string", "null"]},
                    "descripcion": {"type": ["string", "null"]},
                    "metodo_pago": {"type": ["string", "null"]},
                    "es_recurrente": {"type": "boolean"},
                },
                "required": ["tipo", "categoria", "monto", "fecha", "es_recurrente"],
            },
            "nomina": {
                "type": ["object", "null"],
                "properties": {
                    "empleador": {"type": ["string", "null"]},
                    "periodo_inicio": {"type": ["string", "null"]},
                    "periodo_fin": {"type": ["string", "null"]},
                    "fecha_pago": {"type": ["string", "null"]},
                    "percepciones": {"type": "number"},
                    "deducciones": {"type": "number"},
                    "neto_pagado": {"type": "number"},
                    "sueldo_base": {"type": ["number", "null"]},
                    "detalle_percepciones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "concepto": {"type": "string"},
                                "monto": {"type": "number"},
                            },
                        },
                    },
                    "detalle_deducciones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "concepto": {"type": "string"},
                                "monto": {"type": "number"},
                            },
                        },
                    },
                    "moneda": {"type": "string", "default": "MXN"},
                },
                "required": ["percepciones", "deducciones", "neto_pagado"],
            },
        },
        "required": ["tipo_documento"],
    },
}


def _classify_with_anthropic(texto: str) -> dict[str, Any]:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "registrar_documento"},
        messages=[{"role": "user", "content": texto}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise ValueError("El LLM no devolvió una clasificación (sin tool_use en la respuesta)")


def _classify_with_openai(texto: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": texto},
        ],
        tools=[{"type": "function", "function": TOOL_SCHEMA}],
        tool_choice={"type": "function", "function": {"name": "registrar_documento"}},
    )
    tool_call = response.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)


def _classify_with_gemini(texto: str) -> dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.google_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=texto,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT + GEMINI_JSON_SHAPE,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


def classify_document(texto: str) -> ClasificacionResultado:
    if settings.llm_provider == "openai":
        datos = _classify_with_openai(texto)
    elif settings.llm_provider == "anthropic":
        datos = _classify_with_anthropic(texto)
    else:
        datos = _classify_with_gemini(texto)

    tipo_documento = datos["tipo_documento"]

    gasto = None
    nomina = None

    if tipo_documento in ("gasto_personal", "gasto_auto"):
        g = datos.get("gasto")
        if not g:
            raise ValueError(f"tipo_documento={tipo_documento} pero falta el objeto 'gasto'")
        gasto = GastoData(
            tipo=g["tipo"],
            categoria=g["categoria"],
            monto=float(g["monto"]),
            fecha=g["fecha"],
            moneda=g.get("moneda") or "MXN",
            comercio=g.get("comercio"),
            descripcion=g.get("descripcion"),
            metodo_pago=g.get("metodo_pago"),
            es_recurrente=bool(g.get("es_recurrente", False)),
        )
    elif tipo_documento == "recibo_nomina":
        n = datos.get("nomina")
        if not n:
            raise ValueError("tipo_documento=recibo_nomina pero falta el objeto 'nomina'")
        nomina = NominaData(
            percepciones=float(n["percepciones"]),
            deducciones=float(n["deducciones"]),
            neto_pagado=float(n["neto_pagado"]),
            empleador=n.get("empleador"),
            periodo_inicio=n.get("periodo_inicio"),
            periodo_fin=n.get("periodo_fin"),
            fecha_pago=n.get("fecha_pago"),
            detalle_percepciones=n.get("detalle_percepciones") or [],
            detalle_deducciones=n.get("detalle_deducciones") or [],
            moneda=n.get("moneda") or "MXN",
            sueldo_base=float(n["sueldo_base"]) if n.get("sueldo_base") is not None else None,
        )
    else:
        raise ValueError(f"tipo_documento desconocido: {tipo_documento}")

    return ClasificacionResultado(
        tipo_documento=tipo_documento,
        gasto=gasto,
        nomina=nomina,
        respuesta_cruda=datos,
    )
