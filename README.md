# Agente de gastos

Recibe comprobantes (PDF o foto) por correo o por subida manual, extrae los datos con IA,
los clasifica como **gasto personal**, **gasto de auto** o **recibo de nómina**, y los guarda
en PostgreSQL para poder construir después un dashboard con gráficas e indicadores.

## Cómo funciona

1. Llega un comprobante (correo con adjunto, Telegram, o subida manual vía `/upload`)
2. Se extrae el texto: PDF nativo con PyMuPDF; imágenes y PDFs escaneados con Azure Document Intelligence
3. El texto se manda a un LLM (Gemini / Google AI Studio por default) que decide el tipo de documento y estructura los datos
4. Se guarda en `gastos` o `nomina`, y siempre queda un registro en `documentos` (con estado y, si falla, el error)
5. Si algo falla, se manda una alerta por correo

## Requisitos antes de correrlo

Copia `.env.example` a `.env` y llena:

- **Postgres**: usuario/contraseña/nombre de base (puedes dejar los valores de ejemplo en local, pero cámbialos en producción)
- **Azure Document Intelligence**: crea un recurso "Document Intelligence" en el portal de Azure → copia `endpoint` y `key`
- **Google AI Studio (Gemini)**: genera tu llave gratis en aistudio.google.com/apikey → ponla en `GOOGLE_API_KEY` (o, si prefieres Claude/OpenAI, cambia `LLM_PROVIDER` a `anthropic` u `openai` y llena la llave correspondiente)
- **Gmail**: activa verificación en 2 pasos en tu cuenta → genera una "contraseña de aplicación" en myaccount.google.com/apppasswords → úsala en `IMAP_APP_PASSWORD` y `SMTP_APP_PASSWORD` (puede ser la misma)
- **UPLOAD_API_KEY**: cualquier cadena larga y aleatoria, la usarás para autenticar la subida manual
- **Telegram** (opcional): crea un bot con @BotFather → `TELEGRAM_BOT_TOKEN`; consigue tu chat id con @userinfobot → `TELEGRAM_ALLOWED_CHAT_ID` (solo ese chat puede mandarle comprobantes al bot)
- **KM_AUTO_FORWARD_SECRET** (opcional): solo si vas a integrar `km-auto` — mismo valor que pongas como `FORWARD_SECRET` en el `.env` de `km-auto`
- **APP_PORT** (opcional): cambia el puerto donde se expone la API en el host si el 8000 ya está ocupado (ej. en el VPS); por default sigue siendo 8000

## Correr en local

En Windows, lo más simple es doble click en **`iniciar.bat`** — prende Docker si hace falta, levanta todo, y abre el navegador en la API y en Adminer.

Manualmente:

```bash
docker compose up -d --build
docker compose exec -T app python -m app.migrate
```

El segundo comando aplica las migraciones pendientes de `db/migrations/` (idempotente:
si ya están aplicadas no hace nada). `iniciar.bat` ya lo corre solo.

Probar que la API responde:

```bash
curl http://localhost:8000/health
```

Subir un comprobante manualmente:

```bash
curl -X POST http://localhost:8000/upload \
  -H "X-API-Key: <tu UPLOAD_API_KEY>" \
  -F "file=@/ruta/a/tu/ticket.pdf"
```

Revisar el resultado (reemplaza `<id>` por el `documento_id` que devolvió el paso anterior):

```bash
curl http://localhost:8000/documentos/<id> -H "X-API-Key: <tu UPLOAD_API_KEY>"
```

Ver logs del worker de correo (revisa el buzón cada `EMAIL_POLL_INTERVAL_SECONDS`):

```bash
docker compose logs -f worker
```

Consultar directamente la base de datos:

```bash
docker compose exec postgres psql -U gastos -d gastos -c "SELECT id, estado, tipo_documento FROM documentos ORDER BY id DESC LIMIT 5;"
```

### Panel visual

Abre **http://localhost:8000/dashboard/**: es la forma normal de usar el sistema día a día
(subir comprobantes, ver gastos/nómina, gestionar autos y tareas — no hace falta curl ni
Swagger). La primera vez pide la `UPLOAD_API_KEY` (queda guardada en el navegador). Ver la
sección **Ayuda** dentro del panel para instrucciones de los 3 canales de envío.

### Ver los datos sin usar el panel

También se puede navegar la base de datos directo con **Adminer** (incluido en `docker-compose.yml`): abre **http://localhost:8081**, y entra con:
- Sistema: `PostgreSQL`, Servidor: `postgres`, Usuario: `gastos`, Contraseña: la de `POSTGRES_PASSWORD` en tu `.env`, Base de datos: `gastos`

## Desplegar en el VPS

1. Copia la carpeta del proyecto al VPS (o clónala si está en un repositorio git)
2. Copia tu `.env` (no lo subas a un repositorio público)
3. `docker compose up -d --build`
4. Si expones el puerto 8000 a internet, ponle un proxy con HTTPS (ej. Caddy o Nginx) en frente — no lo dejes expuesto sin TLS
5. Considera quitar el `ports: 5432:5432` de Postgres en producción (o limitarlo a `127.0.0.1:5432`) para que no quede expuesto a internet

## Fase 2

- **Gastos recurrentes**: la IA marca `es_recurrente` en cada gasto (renta, suscripciones, seguros anuales, servicios = sí; comida, gasolina, compras puntuales = no)
- **Kilometraje**: en los 3 canales (subida manual, Telegram, correo) puedes escribir `km:45230` en el campo `nota_usuario` del `/upload`, en el caption de Telegram, o en el asunto del correo — se guarda en `gastos.kilometraje` y la nota completa en `documentos.nota_usuario`
- **Aumentos de sueldo**: la IA extrae `sueldo_base` de cada recibo de nómina y lo compara contra el recibo anterior del mismo empleador; si cambia, queda registrado en `nomina_aumentos`. Consulta el historial en `GET /nomina/aumentos`
- **Tareas del auto**: CRUD simple en `/tareas-auto` (crear, listar con filtro `?estado=`, ver una, marcar completada) — cada tarea necesita fecha límite y/o km límite
- **Integración con km-auto**: `POST /webhooks/km-auto` recibe el resumen diario de kilómetros recorridos que manda el proyecto externo `km-auto`, validado con el header `X-Forward-Secret` contra `KM_AUTO_FORWARD_SECRET`, y hace upsert en `km_diario` (por fecha + vehículo, así reenvíos duplicados no generan filas repetidas)
- **Panel visual** en `/dashboard`: menú con Inicio, Documentos, Gastos, Nómina, Mi auto y Ayuda — sube comprobantes, filtra, y administra todo sin usar la API directamente

## Múltiples autos (Mi auto)

- Tabla `autos` (nombre, marca, modelo, año, placas, activo) — se crean/editan desde el panel, en **Mi auto**
- El gasto se asigna solo al vehículo correcto con el tag `auto:nombre` en la nota (mismo mecanismo que `km:`), usando el `nombre` con el que se creó el auto. Si solo hay un vehículo activo, no hace falta etiquetar nada
- **Tareas del auto** ahora quedan ligadas a un vehículo (`tareas_auto.auto_id`) y, al completarse, pueden guardar `costo`, `kilometraje_completado` y **adjuntos** (fotos/PDF de la factura, en `tareas_auto_adjuntos`) vía `POST /tareas-auto/{id}/adjuntos`
- "Cargas de combustible" y "Pagos" en el panel son solo una vista filtrada de `gastos` (categoría `gasolina` vs. el resto) por vehículo — no hay una tabla ni un flujo de captura manual separados; todo sigue entrando por comprobante

## Notas de diseño

- El `hash_archivo` (SHA256) evita procesar el mismo comprobante dos veces
- El endpoint de subida manual y el worker de correo llaman a la misma función `app/pipeline.py::process_document`, así que agregar un canal nuevo (ej. Telegram) solo requiere descargar el archivo y llamar a esa función
- El campo `categoria` es texto libre (no un catálogo con llave foránea) para poder ajustar categorías sin migrar la base de datos
- `db/schema.sql` solo corre una vez al crear el volumen de Postgres; todo cambio de esquema posterior va en `db/migrations/`, aplicado por `app/migrate.py` (sin ORM, sin Alembic — cada migración corre en su propia transacción y queda marcada en `schema_migrations`)
