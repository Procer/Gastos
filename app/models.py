from dataclasses import dataclass, field
from typing import Any, Literal

TipoDocumento = Literal["gasto_personal", "gasto_auto", "recibo_nomina"]

CATEGORIAS_AUTO = {
    "gasolina", "mantenimiento", "seguro", "verificacion", "tenencia",
    "refacciones", "casetas_estacionamiento", "multas", "otro_auto",
}
CATEGORIAS_PERSONAL = {
    "comida", "salud", "entretenimiento", "compras", "servicios",
    "transporte", "otro_personal",
}


@dataclass
class GastoData:
    tipo: str  # 'personal' | 'auto'
    categoria: str
    monto: float
    fecha: str  # 'YYYY-MM-DD'
    moneda: str = "MXN"
    comercio: str | None = None
    descripcion: str | None = None
    metodo_pago: str | None = None
    es_recurrente: bool = False
    kilometraje: int | None = None


@dataclass
class NominaData:
    percepciones: float
    deducciones: float
    neto_pagado: float
    empleador: str | None = None
    periodo_inicio: str | None = None
    periodo_fin: str | None = None
    fecha_pago: str | None = None
    detalle_percepciones: list[dict[str, Any]] = field(default_factory=list)
    detalle_deducciones: list[dict[str, Any]] = field(default_factory=list)
    moneda: str = "MXN"
    sueldo_base: float | None = None


@dataclass
class ClasificacionResultado:
    tipo_documento: TipoDocumento
    gasto: GastoData | None
    nomina: NominaData | None
    respuesta_cruda: dict[str, Any]
