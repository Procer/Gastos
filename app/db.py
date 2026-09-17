import json
from contextlib import contextmanager
from typing import Any

import psycopg2
import psycopg2.extras

from app.config import settings
from app.models import GastoData, NominaData


@contextmanager
def get_connection():
    conn = psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def find_documento_by_hash(hash_archivo: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM documentos WHERE hash_archivo = %s", (hash_archivo,)
            )
            return cur.fetchone()


def insert_documento(
    fuente: str,
    referencia_fuente: str | None,
    hash_archivo: str,
    nombre_archivo_original: str,
    ruta_archivo: str,
    tipo_archivo: str,
    nota_usuario: str | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documentos
                    (fuente, referencia_fuente, hash_archivo, nombre_archivo_original,
                     ruta_archivo, tipo_archivo, nota_usuario, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'procesando')
                RETURNING id
                """,
                (fuente, referencia_fuente, hash_archivo, nombre_archivo_original,
                 ruta_archivo, tipo_archivo, nota_usuario),
            )
            return cur.fetchone()[0]


def update_documento_texto(documento_id: int, texto_extraido: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documentos
                SET texto_extraido = %s, actualizado_en = now()
                WHERE id = %s
                """,
                (texto_extraido, documento_id),
            )


def insert_gasto(documento_id: int, gasto: GastoData) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gastos
                    (documento_id, tipo, categoria, monto, moneda, fecha,
                     comercio, descripcion, metodo_pago, es_recurrente, kilometraje, auto_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (documento_id, gasto.tipo, gasto.categoria, gasto.monto, gasto.moneda,
                 gasto.fecha, gasto.comercio, gasto.descripcion, gasto.metodo_pago,
                 gasto.es_recurrente, gasto.kilometraje, gasto.auto_id),
            )
            return cur.fetchone()[0]


def insert_nomina(documento_id: int, nomina: NominaData) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nomina
                    (documento_id, empleador, periodo_inicio, periodo_fin, fecha_pago,
                     percepciones, deducciones, neto_pagado, sueldo_base,
                     detalle_percepciones, detalle_deducciones, moneda)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (documento_id, nomina.empleador, nomina.periodo_inicio, nomina.periodo_fin,
                 nomina.fecha_pago, nomina.percepciones, nomina.deducciones, nomina.neto_pagado,
                 nomina.sueldo_base,
                 json.dumps(nomina.detalle_percepciones), json.dumps(nomina.detalle_deducciones),
                 nomina.moneda),
            )
            return cur.fetchone()[0]


def find_sueldo_base_anterior(empleador: str, nomina_id_actual: int) -> float | None:
    """Busca el sueldo_base del recibo más reciente de este empleador, excluyendo el actual."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sueldo_base FROM nomina
                WHERE empleador = %s AND id != %s AND sueldo_base IS NOT NULL
                ORDER BY COALESCE(fecha_pago, periodo_inicio) DESC, id DESC
                LIMIT 1
                """,
                (empleador, nomina_id_actual),
            )
            row = cur.fetchone()
            return float(row[0]) if row else None


def insert_nomina_aumento(
    nomina_id: int,
    empleador: str,
    sueldo_base_anterior: float,
    sueldo_base_nuevo: float,
    fecha_pago: str | None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nomina_aumentos
                    (nomina_id, empleador, sueldo_base_anterior, sueldo_base_nuevo, diferencia, fecha_pago)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (nomina_id, empleador, sueldo_base_anterior, sueldo_base_nuevo,
                 sueldo_base_nuevo - sueldo_base_anterior, fecha_pago),
            )
            return cur.fetchone()[0]


def list_nomina_aumentos() -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM nomina_aumentos ORDER BY fecha_pago DESC NULLS LAST, id DESC"
            )
            return cur.fetchall()


def marcar_documento_completado(
    documento_id: int,
    tipo_documento: str,
    respuesta_llm_json: dict[str, Any],
    gasto_id: int | None,
    nomina_id: int | None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documentos
                SET estado = 'completado',
                    tipo_documento = %s,
                    respuesta_llm_json = %s,
                    gasto_id = %s,
                    nomina_id = %s,
                    actualizado_en = now(),
                    procesado_en = now()
                WHERE id = %s
                """,
                (tipo_documento, json.dumps(respuesta_llm_json), gasto_id, nomina_id,
                 documento_id),
            )


def marcar_documento_error(documento_id: int, mensaje_error: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documentos
                SET estado = 'error', mensaje_error = %s, actualizado_en = now()
                WHERE id = %s
                """,
                (mensaje_error, documento_id),
            )


def marcar_alerta_enviada(documento_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documentos SET alerta_enviada = true WHERE id = %s",
                (documento_id,),
            )


def get_documento(documento_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM documentos WHERE id = %s", (documento_id,))
            return cur.fetchone()


def list_documentos(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, fuente, nombre_archivo_original, estado, tipo_documento,
                       mensaje_error, gasto_id, nomina_id, creado_en, procesado_en
                FROM documentos
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


def list_gastos(
    tipo: str | None = None,
    es_recurrente: bool | None = None,
    auto_id: int | None = None,
    categoria: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    condiciones = []
    valores: list[Any] = []
    if tipo:
        condiciones.append("tipo = %s")
        valores.append(tipo)
    if es_recurrente is not None:
        condiciones.append("es_recurrente = %s")
        valores.append(es_recurrente)
    if auto_id is not None:
        condiciones.append("auto_id = %s")
        valores.append(auto_id)
    if categoria:
        condiciones.append("categoria = %s")
        valores.append(categoria)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    valores.append(limit)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM gastos {where} ORDER BY fecha DESC, id DESC LIMIT %s",
                valores,
            )
            return cur.fetchall()


def list_nomina(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM nomina ORDER BY fecha_pago DESC NULLS LAST, id DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()


def list_km_diario(limit: int = 60) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM km_diario ORDER BY fecha DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()


def insert_tarea_auto(
    descripcion: str,
    fecha_limite: str | None,
    km_limite: int | None,
    auto_id: int | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tareas_auto (descripcion, fecha_limite, km_limite, auto_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (descripcion, fecha_limite, km_limite, auto_id),
            )
            return cur.fetchone()[0]


def list_tareas_auto(estado: str | None, auto_id: int | None = None) -> list[dict[str, Any]]:
    condiciones = []
    valores: list[Any] = []
    if estado:
        condiciones.append("estado = %s")
        valores.append(estado)
    if auto_id is not None:
        condiciones.append("auto_id = %s")
        valores.append(auto_id)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM tareas_auto {where} ORDER BY id DESC", valores)
            return cur.fetchall()


def get_tarea_auto(tarea_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tareas_auto WHERE id = %s", (tarea_id,))
            return cur.fetchone()


def completar_tarea_auto(
    tarea_id: int,
    fecha_completada: str | None,
    costo: float | None,
    kilometraje_completado: int | None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tareas_auto
                SET estado = 'completada',
                    fecha_completada = COALESCE(%s, CURRENT_DATE),
                    costo = %s,
                    kilometraje_completado = %s,
                    actualizado_en = now()
                WHERE id = %s
                """,
                (fecha_completada, costo, kilometraje_completado, tarea_id),
            )


def insert_tarea_adjunto(tarea_id: int, nombre_archivo_original: str, ruta_archivo: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tareas_auto_adjuntos (tarea_id, nombre_archivo_original, ruta_archivo)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (tarea_id, nombre_archivo_original, ruta_archivo),
            )
            return cur.fetchone()[0]


def list_tarea_adjuntos(tarea_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM tareas_auto_adjuntos WHERE tarea_id = %s ORDER BY id",
                (tarea_id,),
            )
            return cur.fetchall()


def get_tarea_adjunto(adjunto_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tareas_auto_adjuntos WHERE id = %s", (adjunto_id,))
            return cur.fetchone()


# ---------- Autos ----------


def insert_auto(
    nombre: str, marca: str | None, modelo: str | None, anio: int | None, placas: str | None
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO autos (nombre, marca, modelo, anio, placas)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (nombre, marca, modelo, anio, placas),
            )
            return cur.fetchone()[0]


def list_autos(activo: bool | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if activo is None:
                cur.execute("SELECT * FROM autos ORDER BY id")
            else:
                cur.execute("SELECT * FROM autos WHERE activo = %s ORDER BY id", (activo,))
            return cur.fetchall()


def get_auto(auto_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM autos WHERE id = %s", (auto_id,))
            return cur.fetchone()


def find_auto_by_nombre(nombre: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM autos WHERE LOWER(nombre) = LOWER(%s)", (nombre,))
            return cur.fetchone()


def get_unico_auto_activo() -> dict[str, Any] | None:
    """Si hay exactamente un auto activo registrado, lo devuelve (para asignar gastos sin tag)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM autos WHERE activo = true LIMIT 2")
            filas = cur.fetchall()
            return filas[0] if len(filas) == 1 else None


def update_auto(
    auto_id: int,
    nombre: str | None,
    marca: str | None,
    modelo: str | None,
    anio: int | None,
    placas: str | None,
    activo: bool | None,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE autos
                SET nombre = COALESCE(%s, nombre),
                    marca = COALESCE(%s, marca),
                    modelo = COALESCE(%s, modelo),
                    anio = COALESCE(%s, anio),
                    placas = COALESCE(%s, placas),
                    activo = COALESCE(%s, activo)
                WHERE id = %s
                """,
                (nombre, marca, modelo, anio, placas, activo, auto_id),
            )


def upsert_km_diario(fecha: str, vehiculo: str, km: float, resumen: dict[str, Any]) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO km_diario (fecha, vehiculo, km, resumen_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (fecha, vehiculo) DO UPDATE
                SET km = EXCLUDED.km,
                    resumen_json = EXCLUDED.resumen_json,
                    actualizado_en = now()
                """,
                (fecha, vehiculo, km, json.dumps(resumen)),
            )
