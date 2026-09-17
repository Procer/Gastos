CREATE TABLE tareas_auto (
    id             BIGSERIAL PRIMARY KEY,
    descripcion    TEXT           NOT NULL,
    fecha_limite   DATE,
    km_limite      INTEGER,
    estado         VARCHAR(20)    NOT NULL DEFAULT 'pendiente',  -- pendiente|completada
    creado_en      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT chk_tareas_auto_limite CHECK (fecha_limite IS NOT NULL OR km_limite IS NOT NULL)
);

CREATE INDEX idx_tareas_auto_estado ON tareas_auto (estado);
