CREATE TABLE autos (
    id          BIGSERIAL PRIMARY KEY,
    nombre      VARCHAR(50)   NOT NULL,   -- identificador corto usado en el tag "auto:nombre" (ej. "sedan")
    marca       VARCHAR(100),
    modelo      VARCHAR(100),
    anio        INTEGER,
    placas      VARCHAR(20),
    activo      BOOLEAN       NOT NULL DEFAULT true,
    creado_en   TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_autos_nombre ON autos (LOWER(nombre));
