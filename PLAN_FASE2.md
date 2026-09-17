# Plan — Fase 2 del Agente de Gastos

Plan para la siguiente sesión de trabajo. Nada de esto está implementado todavía.

## Contexto

La Fase 1 (procesamiento de comprobantes: correo, Telegram, subida manual → extracción → clasificación con IA → PostgreSQL) ya está construida y probada. Esta fase agrega: distinguir gastos recurrentes, detectar aumentos de sueldo, capturar kilometraje del auto, tareas/recordatorios del auto, e integrar el proyecto externo `km-auto` (ya en producción en el mismo VPS) para llevar control real de kilómetros recorridos.

## 0. Mecanismo de migraciones (prerequisito de todo lo demás)

`db/schema.sql` solo corre una vez al crear el volumen de Postgres, y ya hay datos reales cargados — no se puede seguir editando ese archivo. Se agrega:

- `db/migrations/001_gastos_recurrente.sql`, `002_gastos_km_y_nota.sql`, `003_nomina_sueldo_base.sql`, `004_tareas_auto.sql`, `005_km_diario.sql`
- `app/migrate.py`: script chico que crea una tabla `schema_migrations`, revisa qué archivos de `db/migrations/` no se han aplicado, y los corre uno por uno (cada uno en su propia transacción — si falla, no queda marcado como aplicado, así que reintentar es seguro). Sin Alembic, sin ORM.
- `Dockerfile`: falta `COPY db ./db` (hoy solo copia `app/`) — se agrega.
- `iniciar.bat`: después de `docker compose up -d`, se agrega `docker compose exec -T app python -m app.migrate` — así las migraciones se aplican solas cada vez que se abre el sistema, sin que el usuario tenga que hacer nada a mano.

## 1. Gastos: fijos/recurrentes vs. variables

- Migración: `ALTER TABLE gastos ADD COLUMN es_recurrente BOOLEAN NOT NULL DEFAULT false;`
- La IA lo clasifica automáticamente (no lo llena el usuario): se agrega al prompt y al schema de `llm_classifier.py`, con ejemplos (renta, suscripciones, seguros anuales, servicios = recurrente; comida, gasolina, compras puntuales = variable).
- Los 2 comprobantes ya cargados quedan en `false` por default (opcional: reclasificarlos después reusando el texto ya guardado).

## 2. Kilometraje del auto + nota de usuario (en los 3 canales)

- Un ticket de gasolina no trae el km impreso — el usuario lo escribe a mano junto con el comprobante, con la convención `km:45230` (tolerante a variantes: `km 45230`, `km=45230`, `KM: 45,230`).
- Migraciones: `gastos.kilometraje` (entero) y `documentos.nota_usuario` (texto libre completo, para trazabilidad y para dejar espacio a futuro para la palabra clave del auto cuando se retome multi-auto, ej. `km:45230 auto:sedan`, sin necesitar otra migración).
- Nuevo `app/km_parser.py` con un regex tolerante que extrae el número.
- Se conecta en los 3 canales: campo `Form` opcional en `/upload`, `caption` de Telegram, asunto del correo (decodificado con `email.header.decode_header` porque puede venir en formato MIME).
- El kilometraje NO se le pide a la IA — es un dato aparte que el usuario escribe, no algo que el LLM deba adivinar del comprobante.

## 3. Nómina: detectar aumentos + informe

- Se compara por **`sueldo_base`** (nuevo campo que el LLM extrae explícitamente), no por el total de percepciones — el total incluye bonos/horas extra/aguinaldo que son variables y generarían falsos positivos de "aumento" mes a mes.
- Migración: `nomina.sueldo_base NUMERIC(12,2)`.
- Al guardar un nuevo recibo, se compara contra el recibo anterior del mismo empleador:
  - Primer recibo de ese empleador → no hay comparación (no es un "aumento" falso)
  - Falta `sueldo_base` en cualquiera de los dos → no se compara (mejor no comparar que arriesgar un falso positivo)
  - Diferencia > 1 centavo → se registra como aumento/reducción
- **Importante**: esta comparación corre en un try/except separado, después de que el documento ya se guardó como completado — si la comparación falla, nunca debe tumbar el documento a estado "error".
- Nuevo endpoint `GET /nomina/aumentos` — informe en JSON del historial de aumentos (sin dashboard todavía).

## 4. Tareas/recordatorios del auto (no son gastos)

- Nueva tabla `tareas_auto`: descripción, fecha límite y/o km límite (al menos uno de los dos obligatorio), estado (pendiente/completada).
- Endpoints CRUD simples en `main.py` (sin router aparte, igual que el resto): crear, listar (filtro por estado), ver una, marcar completada.
- Sin creación automática por IA en esta fase — solo manual vía Swagger.

## 5. Integración con km-auto (kilómetros reales recorridos)

`km-auto` (proyecto externo, ya en el VPS, Node.js con pm2, sin Docker) ya tiene un mecanismo de reenvío diario integrado y sin usar: si se le configura `FORWARD_URL`/`FORWARD_SECRET`, cada noche a las 23:59 manda un `POST` con el resumen del día (km recorridos, con header `x-forward-secret`).

- Nueva tabla `km_diario` en Gastos: fecha + vehículo (string libre, así diferenciamos autos a futuro) + los km/metros del resumen + el JSON completo guardado por si acaso. Índice único en `(fecha, vehiculo)`.
- Nuevo endpoint `POST /webhooks/km-auto` en Gastos: valida el header `x-forward-secret` contra `KM_AUTO_FORWARD_SECRET` (nueva variable de entorno), y guarda con **upsert** (`ON CONFLICT (fecha, vehiculo) DO UPDATE`) — así reenvíos duplicados de km-auto nunca generan filas repetidas.
- Configuración externa que el usuario debe poner él mismo en el `.env` de **km-auto** (no es código de este repo): `FORWARD_URL=https://<dominio-de-gastos>/webhooks/km-auto` y `FORWARD_SECRET=<mismo valor>`.
- Opcional: backfill del histórico pasado usando `GET /api/daily?k=ADMIN_TOKEN` que km-auto ya expone.

## 6. Puerto 8000 — conflicto en el VPS

El VPS donde se desplegará `Gastos` ya tiene otra app usando el puerto 8000. Se cambia `docker-compose.yml` para que el puerto sea configurable (`APP_PORT`, default 8000 para no romper el uso local) y se ligue solo a `127.0.0.1` (nginx hace de frente en el VPS, igual que con las demás apps).

## Orden sugerido para la próxima sesión

1. Infra de migraciones (prerequisito de todo)
2. Gasto recurrente vs. variable
3. Kilometraje + nota de usuario (3 canales)
4. Nómina: sueldo_base + comparación + informe de aumentos
5. Tareas del auto (CRUD)
6. Webhook de km-auto
7. Puerto configurable (se puede hacer en cualquier momento, no urgente hasta desplegar al VPS)

Cada fase tiene su propia migración y se puede probar por separado antes de seguir con la siguiente.
