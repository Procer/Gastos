-- Esquema de base de datos para el agente de gastos.
-- Se monta en /docker-entrypoint-initdb.d/ y Postgres lo ejecuta solo la primera vez
-- que se crea el volumen de datos.

CREATE TABLE documentos (
    id                      BIGSERIAL PRIMARY KEY,
    fuente                  VARCHAR(20)   NOT NULL,                     -- 'email' | 'manual' | 'telegram'
    referencia_fuente       TEXT,                                       -- message-id del correo, o NULL si es manual
    hash_archivo            CHAR(64)      NOT NULL,                     -- SHA256 del archivo, evita reprocesar duplicados
    nombre_archivo_original TEXT          NOT NULL,
    ruta_archivo            TEXT          NOT NULL,                     -- ruta dentro del volumen /app/uploads
    tipo_archivo            VARCHAR(10)   NOT NULL,                     -- 'pdf' | 'imagen'
    estado                  VARCHAR(20)   NOT NULL DEFAULT 'pendiente', -- pendiente|procesando|completado|error|duplicado
    tipo_documento          VARCHAR(20),                                -- gasto_personal|gasto_auto|recibo_nomina
    texto_extraido          TEXT,
    respuesta_llm_json      JSONB,
    mensaje_error           TEXT,
    alerta_enviada          BOOLEAN       NOT NULL DEFAULT false,
    gasto_id                BIGINT,
    nomina_id               BIGINT,
    creado_en               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    actualizado_en          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    procesado_en            TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_documentos_hash ON documentos (hash_archivo);
CREATE INDEX idx_documentos_estado ON documentos (estado);
CREATE INDEX idx_documentos_tipo_documento ON documentos (tipo_documento);
CREATE INDEX idx_documentos_creado_en ON documentos (creado_en);

CREATE TABLE gastos (
    id            BIGSERIAL PRIMARY KEY,
    documento_id  BIGINT REFERENCES documentos(id),
    tipo          VARCHAR(20)    NOT NULL,          -- 'personal' | 'auto'
    categoria     VARCHAR(50)    NOT NULL,
    monto         NUMERIC(12,2)  NOT NULL,
    moneda        VARCHAR(3)     NOT NULL DEFAULT 'MXN',
    fecha         DATE           NOT NULL,
    comercio      VARCHAR(255),
    descripcion   TEXT,
    metodo_pago   VARCHAR(30),
    creado_en     TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX idx_gastos_fecha ON gastos (fecha);
CREATE INDEX idx_gastos_tipo_categoria_fecha ON gastos (tipo, categoria, fecha);

CREATE TABLE nomina (
    id                     BIGSERIAL PRIMARY KEY,
    documento_id           BIGINT REFERENCES documentos(id),
    empleador              VARCHAR(255),
    periodo_inicio         DATE,
    periodo_fin            DATE,
    fecha_pago             DATE,
    percepciones           NUMERIC(12,2)  NOT NULL,
    deducciones            NUMERIC(12,2)  NOT NULL,
    neto_pagado            NUMERIC(12,2)  NOT NULL,
    detalle_percepciones   JSONB,
    detalle_deducciones    JSONB,
    moneda                 VARCHAR(3)     NOT NULL DEFAULT 'MXN',
    creado_en              TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX idx_nomina_fecha_pago ON nomina (fecha_pago);
CREATE INDEX idx_nomina_periodo_inicio ON nomina (periodo_inicio);
