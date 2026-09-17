ALTER TABLE tareas_auto ADD COLUMN fecha_completada DATE;
ALTER TABLE tareas_auto ADD COLUMN costo NUMERIC(12,2);
ALTER TABLE tareas_auto ADD COLUMN kilometraje_completado INTEGER;

CREATE TABLE tareas_auto_adjuntos (
    id                      BIGSERIAL PRIMARY KEY,
    tarea_id                BIGINT       NOT NULL REFERENCES tareas_auto(id),
    nombre_archivo_original TEXT         NOT NULL,
    ruta_archivo            TEXT         NOT NULL,
    subido_en               TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_tareas_auto_adjuntos_tarea_id ON tareas_auto_adjuntos (tarea_id);
