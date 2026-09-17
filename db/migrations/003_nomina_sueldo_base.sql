ALTER TABLE nomina ADD COLUMN sueldo_base NUMERIC(12,2);

CREATE TABLE nomina_aumentos (
    id                  BIGSERIAL PRIMARY KEY,
    nomina_id           BIGINT REFERENCES nomina(id),
    empleador           VARCHAR(255)   NOT NULL,
    sueldo_base_anterior NUMERIC(12,2) NOT NULL,
    sueldo_base_nuevo    NUMERIC(12,2) NOT NULL,
    diferencia           NUMERIC(12,2) NOT NULL,
    fecha_pago           DATE,
    creado_en            TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_nomina_aumentos_empleador ON nomina_aumentos (empleador);
