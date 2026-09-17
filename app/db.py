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
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documentos
                    (fuente, referencia_fuente, hash_archivo, nombre_archivo_original,
                     ruta_archivo, tipo_archivo, estado)
                VALUES (%s, %s, %s, %s, %s, %s, 'procesando')
                RETURNING id
                """,
                (fuente, referencia_fuente, hash_archivo, nombre_archivo_original,
                 ruta_archivo, tipo_archivo),
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
                     comercio, descripcion, metodo_pago)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (documento_id, gasto.tipo, gasto.categoria, gasto.monto, gasto.moneda,
                 gasto.fecha, gasto.comercio, gasto.descripcion, gasto.metodo_pago),
            )
            return cur.fetchone()[0]


def insert_nomina(documento_id: int, nomina: NominaData) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nomina
                    (documento_id, empleador, periodo_inicio, periodo_fin, fecha_pago,
                     percepciones, deducciones, neto_pagado,
                     detalle_percepciones, detalle_deducciones, moneda)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (documento_id, nomina.empleador, nomina.periodo_inicio, nomina.periodo_fin,
                 nomina.fecha_pago, nomina.percepciones, nomina.deducciones, nomina.neto_pagado,
                 json.dumps(nomina.detalle_percepciones), json.dumps(nomina.detalle_deducciones),
                 nomina.moneda),
            )
            return cur.fetchone()[0]


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
