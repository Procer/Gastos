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
                     comercio, descripcion, metodo_pago, es_recurrente, kilometraje)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (documento_id, gasto.tipo, gasto.categoria, gasto.monto, gasto.moneda,
                 gasto.fecha, gasto.comercio, gasto.descripcion, gasto.metodo_pago,
                 gasto.es_recurrente, gasto.kilometraje),
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


def insert_tarea_auto(
    descripcion: str, fecha_limite: str | None, km_limite: int | None
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tareas_auto (descripcion, fecha_limite, km_limite)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (descripcion, fecha_limite, km_limite),
            )
            return cur.fetchone()[0]


def list_tareas_auto(estado: str | None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if estado:
                cur.execute(
                    "SELECT * FROM tareas_auto WHERE estado = %s ORDER BY id DESC", (estado,)
                )
            else:
                cur.execute("SELECT * FROM tareas_auto ORDER BY id DESC")
            return cur.fetchall()


def get_tarea_auto(tarea_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tareas_auto WHERE id = %s", (tarea_id,))
            return cur.fetchone()


def completar_tarea_auto(tarea_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tareas_auto
                SET estado = 'completada', actualizado_en = now()
                WHERE id = %s
                """,
                (tarea_id,),
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
