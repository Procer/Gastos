CREATE TABLE km_diario (
    id             BIGSERIAL PRIMARY KEY,
    fecha          DATE           NOT NULL,
    vehiculo       VARCHAR(50)    NOT NULL DEFAULT 'default',
    km             NUMERIC(10,2)  NOT NULL,
    resumen_json   JSONB          NOT NULL,
    creado_en      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_km_diario_fecha_vehiculo ON km_diario (fecha, vehiculo);
