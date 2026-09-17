ALTER TABLE gastos ADD COLUMN auto_id BIGINT REFERENCES autos(id);
ALTER TABLE tareas_auto ADD COLUMN auto_id BIGINT REFERENCES autos(id);

CREATE INDEX idx_gastos_auto_id ON gastos (auto_id);
CREATE INDEX idx_tareas_auto_auto_id ON tareas_auto (auto_id);
