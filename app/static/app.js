const API_KEY_STORAGE_KEY = "gastos_dashboard_api_key";

function getApiKey() {
  try {
    return localStorage.getItem(API_KEY_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function setApiKey(valor) {
  try {
    localStorage.setItem(API_KEY_STORAGE_KEY, valor);
  } catch {
    /* modo privado del navegador: la key solo dura esta sesión de pestaña */
  }
}

function marcarEstadoKey(ok, mensaje) {
  const el = document.getElementById("apiKeyEstado");
  el.textContent = mensaje;
  el.className = "estado-key " + (ok ? "ok" : "error");
}

async function apiFetch(path, opts = {}) {
  const apiKey = getApiKey();
  const headers = Object.assign({}, opts.headers, { "X-API-Key": apiKey });
  const resp = await fetch(path, Object.assign({}, opts, { headers }));
  if (resp.status === 401) {
    marcarEstadoKey(false, "API key inválida");
    throw new Error("API key inválida");
  }
  if (!resp.ok) {
    const detalle = await resp.text();
    throw new Error(`Error ${resp.status}: ${detalle}`);
  }
  marcarEstadoKey(true, "conectado");
  return resp.status === 204 ? null : resp.json();
}

function formatoMoneda(valor) {
  if (valor === null || valor === undefined) return "—";
  return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(valor);
}

function formatoFecha(valor) {
  if (!valor) return "—";
  return String(valor).slice(0, 10);
}

function celda(texto) {
  const td = document.createElement("td");
  td.textContent = texto === null || texto === undefined || texto === "" ? "—" : texto;
  return td;
}

function badgeEstado(estado) {
  const td = document.createElement("td");
  const span = document.createElement("span");
  span.className = `badge badge-${estado}`;
  span.textContent = estado;
  td.appendChild(span);
  return td;
}

function limpiarTabla(idTabla, columnas) {
  const tbody = document.querySelector(`#${idTabla} tbody`);
  tbody.innerHTML = "";
  return tbody;
}

function filaVacia(tbody, columnas, texto = "Sin datos todavía") {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = columnas;
  td.className = "vacio";
  td.textContent = texto;
  tr.appendChild(td);
  tbody.appendChild(tr);
}

// ---------- Documentos ----------

async function cargarDocumentos() {
  const datos = await apiFetch("/documentos?limit=50");
  const tbody = limpiarTabla("tablaDocumentos");
  if (!datos.length) return filaVacia(tbody, 6);
  for (const d of datos) {
    const tr = document.createElement("tr");
    tr.appendChild(celda(d.id));
    tr.appendChild(celda(d.fuente));
    tr.appendChild(celda(d.nombre_archivo_original));
    tr.appendChild(badgeEstado(d.estado));
    tr.appendChild(celda(d.tipo_documento));
    tr.appendChild(celda(formatoFecha(d.creado_en)));
    tbody.appendChild(tr);
  }
}

// ---------- Gastos ----------

let chartCategorias, chartRecurrencia;

async function cargarGastos() {
  const tipo = document.getElementById("filtroTipo").value;
  const esRecurrente = document.getElementById("filtroRecurrente").value;
  const params = new URLSearchParams({ limit: "200" });
  if (tipo) params.set("tipo", tipo);
  if (esRecurrente) params.set("es_recurrente", esRecurrente);

  const datos = await apiFetch(`/gastos?${params.toString()}`);

  const tbody = limpiarTabla("tablaGastos");
  if (!datos.length) {
    filaVacia(tbody, 7);
  } else {
    for (const g of datos) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(formatoFecha(g.fecha)));
      tr.appendChild(celda(g.tipo));
      tr.appendChild(celda(g.categoria));
      tr.appendChild(celda(g.comercio));
      tr.appendChild(celda(formatoMoneda(g.monto)));
      tr.appendChild(celda(g.es_recurrente ? "Sí" : "No"));
      tr.appendChild(celda(g.kilometraje));
      tbody.appendChild(tr);
    }
  }

  // resumen: gasto del mes actual + conteo recurrente/variable del mes
  const hoy = new Date();
  const mesActual = hoy.toISOString().slice(0, 7);
  const delMes = datos.filter((g) => String(g.fecha).slice(0, 7) === mesActual);
  const totalMes = delMes.reduce((acc, g) => acc + Number(g.monto), 0);
  document.getElementById("resGastoMes").textContent = formatoMoneda(totalMes);
  const recurrentes = delMes.filter((g) => g.es_recurrente).length;
  const variables = delMes.length - recurrentes;
  document.getElementById("resRecurrentes").textContent = `${recurrentes} / ${variables}`;

  // gráfica de categorías (suma de monto por categoría)
  const porCategoria = {};
  for (const g of datos) {
    porCategoria[g.categoria] = (porCategoria[g.categoria] || 0) + Number(g.monto);
  }
  const etiquetasCategoria = Object.keys(porCategoria);
  const valoresCategoria = Object.values(porCategoria);

  if (chartCategorias) chartCategorias.destroy();
  chartCategorias = new Chart(document.getElementById("chartCategorias"), {
    type: "bar",
    data: {
      labels: etiquetasCategoria,
      datasets: [{ label: "Gasto por categoría", data: valoresCategoria, backgroundColor: "#5b8def" }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: "#93a0bd" } }, y: { ticks: { color: "#93a0bd" } } },
    },
  });

  // gráfica recurrente vs variable (conteo total, no solo del mes)
  const totalRecurrente = datos.filter((g) => g.es_recurrente).length;
  const totalVariable = datos.length - totalRecurrente;

  if (chartRecurrencia) chartRecurrencia.destroy();
  chartRecurrencia = new Chart(document.getElementById("chartRecurrencia"), {
    type: "doughnut",
    data: {
      labels: ["Recurrente", "Variable"],
      datasets: [{ data: [totalRecurrente, totalVariable], backgroundColor: ["#3ecf8e", "#f0b429"] }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { color: "#93a0bd" } } },
    },
  });
}

// ---------- Nómina ----------

async function cargarNomina() {
  const [nomina, aumentos] = await Promise.all([
    apiFetch("/nomina?limit=50"),
    apiFetch("/nomina/aumentos"),
  ]);

  const tbodyNomina = limpiarTabla("tablaNomina");
  if (!nomina.length) {
    filaVacia(tbodyNomina, 6);
  } else {
    for (const n of nomina) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(formatoFecha(n.fecha_pago)));
      tr.appendChild(celda(n.empleador));
      tr.appendChild(celda(formatoMoneda(n.sueldo_base)));
      tr.appendChild(celda(formatoMoneda(n.percepciones)));
      tr.appendChild(celda(formatoMoneda(n.deducciones)));
      tr.appendChild(celda(formatoMoneda(n.neto_pagado)));
      tbodyNomina.appendChild(tr);
    }
  }

  const tbodyAumentos = limpiarTabla("tablaAumentos");
  if (!aumentos.length) {
    filaVacia(tbodyAumentos, 5);
  } else {
    for (const a of aumentos) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(formatoFecha(a.fecha_pago)));
      tr.appendChild(celda(a.empleador));
      tr.appendChild(celda(formatoMoneda(a.sueldo_base_anterior)));
      tr.appendChild(celda(formatoMoneda(a.sueldo_base_nuevo)));
      tr.appendChild(celda(formatoMoneda(a.diferencia)));
      tbodyAumentos.appendChild(tr);
    }
  }

  document.getElementById("resAumentos").textContent = aumentos.length;
}

// ---------- Tareas del auto ----------

async function completarTarea(id) {
  await apiFetch(`/tareas-auto/${id}/completar`, { method: "POST" });
  await cargarTareas();
}

async function cargarTareas() {
  const estado = document.getElementById("filtroEstadoTarea").value;
  const params = new URLSearchParams();
  if (estado) params.set("estado", estado);

  const datos = await apiFetch(`/tareas-auto?${params.toString()}`);
  const tbody = limpiarTabla("tablaTareas");
  if (!datos.length) {
    filaVacia(tbody, 5);
  } else {
    for (const t of datos) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(t.descripcion));
      tr.appendChild(celda(formatoFecha(t.fecha_limite)));
      tr.appendChild(celda(t.km_limite));
      tr.appendChild(badgeEstado(t.estado));
      const tdAccion = document.createElement("td");
      if (t.estado === "pendiente") {
        const btn = document.createElement("button");
        btn.className = "small";
        btn.textContent = "Completar";
        btn.onclick = () => completarTarea(t.id);
        tdAccion.appendChild(btn);
      }
      tr.appendChild(tdAccion);
      tbody.appendChild(tr);
    }
  }

  const pendientes = await apiFetch("/tareas-auto?estado=pendiente");
  document.getElementById("resTareas").textContent = pendientes.length;
}

// ---------- Kilometraje diario ----------

let chartKm;

async function cargarKm() {
  const datos = await apiFetch("/km-diario?limit=60");
  const ordenados = [...datos].reverse();

  const tbody = limpiarTabla("tablaKm");
  if (!datos.length) {
    filaVacia(tbody, 3);
  } else {
    for (const k of datos) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(formatoFecha(k.fecha)));
      tr.appendChild(celda(k.vehiculo));
      tr.appendChild(celda(k.km));
      tbody.appendChild(tr);
    }
  }

  if (chartKm) chartKm.destroy();
  chartKm = new Chart(document.getElementById("chartKm"), {
    type: "line",
    data: {
      labels: ordenados.map((k) => formatoFecha(k.fecha)),
      datasets: [
        {
          label: "Km recorridos",
          data: ordenados.map((k) => k.km),
          borderColor: "#5b8def",
          backgroundColor: "rgba(91,141,239,0.2)",
          tension: 0.25,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: "#93a0bd" } }, y: { ticks: { color: "#93a0bd" } } },
    },
  });
}

// ---------- Subir comprobante ----------

async function pollDocumento(id) {
  for (let intento = 0; intento < 20; intento++) {
    const doc = await apiFetch(`/documentos/${id}`);
    if (doc.estado !== "procesando") return doc;
    await new Promise((r) => setTimeout(r, 1500));
  }
  return apiFetch(`/documentos/${id}`);
}

async function manejarSubmitSubir(ev) {
  ev.preventDefault();
  const archivo = document.getElementById("archivoInput").files[0];
  const nota = document.getElementById("notaInput").value;
  const resultado = document.getElementById("subirResultado");
  if (!archivo) return;

  resultado.className = "";
  resultado.textContent = "Subiendo y procesando (puede tardar unos segundos)...";

  const formData = new FormData();
  formData.append("file", archivo);
  if (nota) formData.append("nota_usuario", nota);

  try {
    const subida = await apiFetch("/upload", { method: "POST", body: formData });
    const doc = await pollDocumento(subida.documento_id);

    if (doc.estado === "completado") {
      resultado.className = "ok";
      resultado.textContent = `Documento #${doc.id} completado como "${doc.tipo_documento}".`;
    } else if (doc.estado === "duplicado") {
      resultado.className = "";
      resultado.textContent = `Documento #${doc.id}: ya existía (duplicado), no se reprocesó.`;
    } else if (doc.estado === "error") {
      resultado.className = "error";
      resultado.textContent = `Documento #${doc.id} terminó en error: ${doc.mensaje_error || "sin detalle"}`;
    } else {
      resultado.className = "";
      resultado.textContent = `Documento #${doc.id} sigue en estado "${doc.estado}", revisa en unos segundos.`;
    }

    document.getElementById("formSubir").reset();
    await cargarTodo();
  } catch (err) {
    resultado.className = "error";
    resultado.textContent = "Error al subir: " + err.message;
  }
}

// ---------- Orquestación ----------

async function cargarTodo() {
  const apiKey = getApiKey();
  if (!apiKey) {
    marcarEstadoKey(false, "sin API key");
    return;
  }
  try {
    await Promise.all([cargarDocumentos(), cargarGastos(), cargarNomina(), cargarTareas(), cargarKm()]);
  } catch (err) {
    console.error(err);
  }
}

function init() {
  const input = document.getElementById("apiKeyInput");
  input.value = getApiKey();
  if (getApiKey()) marcarEstadoKey(true, "guardada");

  document.getElementById("btnGuardarKey").addEventListener("click", () => {
    setApiKey(input.value.trim());
    cargarTodo();
  });

  document.getElementById("formSubir").addEventListener("submit", manejarSubmitSubir);
  document.getElementById("filtroTipo").addEventListener("change", cargarGastos);
  document.getElementById("filtroRecurrente").addEventListener("change", cargarGastos);
  document.getElementById("filtroEstadoTarea").addEventListener("change", cargarTareas);

  document.getElementById("formTarea").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const descripcion = document.getElementById("tareaDescripcion").value;
    const fechaLimite = document.getElementById("tareaFechaLimite").value || null;
    const kmLimite = document.getElementById("tareaKmLimite").value || null;
    if (!fechaLimite && !kmLimite) {
      alert("Indica al menos fecha límite o km límite");
      return;
    }
    await apiFetch("/tareas-auto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        descripcion,
        fecha_limite: fechaLimite,
        km_limite: kmLimite ? Number(kmLimite) : null,
      }),
    });
    document.getElementById("formTarea").reset();
    await cargarTareas();
  });

  cargarTodo();
}

document.addEventListener("DOMContentLoaded", init);
