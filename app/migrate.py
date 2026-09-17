import logging
from pathlib import Path

import psycopg2

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"


def _connect():
    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )


def _ensure_schema_migrations_table() -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     VARCHAR(255) PRIMARY KEY,
                    aplicada_en TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


def _migraciones_aplicadas() -> set[str]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def _aplicar_migracion(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
        conn.commit()
        logger.info("Migración aplicada: %s", path.name)
    except Exception:
        conn.rollback()
        logger.exception("Falló la migración %s, no queda marcada como aplicada", path.name)
        raise
    finally:
        conn.close()


def run_migrations() -> None:
    """Aplica las migraciones de db/migrations/ que falten, en orden alfabético.

    Cada migración corre en su propia transacción (la marca en `schema_migrations`
    se inserta en la misma transacción que su SQL), así que si una falla no queda
    marcada como aplicada y reintentar en el siguiente arranque es seguro.
    """
    _ensure_schema_migrations_table()
    aplicadas = _migraciones_aplicadas()

    pendientes = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in aplicadas)
    if not pendientes:
        logger.info("No hay migraciones pendientes")
        return

    for path in pendientes:
        _aplicar_migracion(path)


if __name__ == "__main__":
    run_migrations()
