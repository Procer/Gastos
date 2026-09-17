const API_KEY_STORAGE_KEY = "gastos_dashboard_api_key";
const VISTAS = ["inicio", "documentos", "gastos", "nomina", "mi-auto", "ayuda"];

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

function escapeAttr(valor) {
  return String(valor ?? "").replace(/"/g, "&quot;");
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

function limpiarTabla(idTabla) {
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

// ---------- Modal ----------

function abrirModal(titulo, htmlBody) {
  document.getElementById("modalTitulo").textContent = titulo;
  document.getElementById("modalBody").innerHTML = htmlBody;
  document.getElementById("modalOverlay").classList.remove("hidden");
}

function cerrarModal() {
  document.getElementById("modalOverlay").classList.add("hidden");
  document.getElementById("modalBody").innerHTML = "";
}

// ---------- Router ----------

function aplicarVistaDesdeHash() {
  const solicitada = window.location.hash.replace("#", "") || "inicio";
  const nombre = VISTAS.includes(solicitada) ? solicitada : "inicio";

  for (const v of VISTAS) {
    document.getElementById(`view-${v}`).classList.toggle("hidden", v !== nombre);
  }
  for (const btn of document.querySelectorAll(".nav-link")) {
    btn.classList.toggle("active", btn.dataset.view === nombre);
  }

  cargarVista(nombre);
}

function cargarVista(nombre) {
  if (!getApiKey()) {
    marcarEstadoKey(false, "sin API key");
    return;
  }
  const cargadores = {
    inicio: cargarInicio,
    documentos: cargarDocumentos,
    gastos: cargarGastos,
    nomina: cargarNomina,
    "mi-auto": cargarMiAuto,
    ayuda: cargarAyuda,
  };
  const cargador = cargadores[nombre];
  if (cargador) cargador().catch((err) => console.error(err));
}

// ---------- Inicio ----------

async function cargarInicio() {
  const [gastos, tareasPendientes, aumentos] = await Promise.all([
    apiFetch("/gastos?limit=500"),
    apiFetch("/tareas-auto?estado=pendiente"),
    apiFetch("/nomina/aumentos"),
  ]);

  const hoy = new Date();
  const mesActual = hoy.toISOString().slice(0, 7);
  const delMes = gastos.filter((g) => String(g.fecha).slice(0, 7) === mesActual);
  const totalMes = delMes.reduce((acc, g) => acc + Number(g.monto), 0);
  document.getElementById("resGastoMes").textContent = formatoMoneda(totalMes);

  const recurrentes = delMes.filter((g) => g.es_recurrente).length;
  const variables = delMes.length - recurrentes;
  document.getElementById("resRecurrentes").textContent = `${recurrentes} / ${variables}`;

  document.getElementById("resTareas").textContent = tareasPendientes.length;
  document.getElementById("resAumentos").textContent = aumentos.length;
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
  const params = new URLSearchParams({ limit: "300" });
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

  const porCategoria = {};
  for (const g of datos) {
    porCategoria[g.categoria] = (porCategoria[g.categoria] || 0) + Number(g.monto);
  }

  if (chartCategorias) chartCategorias.destroy();
  chartCategorias = new Chart(document.getElementById("chartCategorias"), {
    type: "bar",
    data: {
      labels: Object.keys(porCategoria),
      datasets: [{ label: "Gasto por categoría", data: Object.values(porCategoria), backgroundColor: "#5b8def" }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: "#93a0bd" } }, y: { ticks: { color: "#93a0bd" } } },
    },
  });

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
}

// ---------- Mi auto ----------

let autosCache = [];
let autoSeleccionadoId = "todos";
let subtabActual = "cargas";
let miAutoInicializado = false;
let chartKmAuto;

async function cargarMiAuto() {
  const autos = await apiFetch("/autos");
  autosCache = autos;

  if (!miAutoInicializado && autos.length > 0) {
    const activos = autos.filter((a) => a.activo);
    autoSeleccionadoId = activos.length === 1 ? activos[0].id : "todos";
    miAutoInicializado = true;
  }

  renderSelectorAutos(autos);
  renderAutosGrid(autos);
  await cargarSubtabActual();
}

function renderSelectorAutos(autos) {
  const select = document.getElementById("filtroAutoSeleccionado");
  select.innerHTML = "";
  const optTodos = document.createElement("option");
  optTodos.value = "todos";
  optTodos.textContent = "Todos los vehículos";
  select.appendChild(optTodos);
  for (const auto of autos) {
    const opt = document.createElement("option");
    opt.value = String(auto.id);
    opt.textContent = auto.nombre + (auto.activo ? "" : " (inactivo)");
    select.appendChild(opt);
  }
  select.value = String(autoSeleccionadoId);
}

function renderAutosGrid(autos) {
  const grid = document.getElementById("autosGrid");
  grid.innerHTML = "";

  for (const auto of autos) {
    const card = document.createElement("div");
    card.className =
      "auto-card" +
      (auto.id === autoSeleccionadoId ? " selected" : "") +
      (!auto.activo ? " inactivo" : "");

    const info = document.createElement("div");
    info.innerHTML = `
      <h4>${auto.nombre}</h4>
      <div class="muted">${[auto.marca, auto.modelo, auto.anio].filter(Boolean).join(" ") || "—"}</div>
      <div class="muted">${auto.placas || ""}</div>
    `;
    card.appendChild(info);

    const acciones = document.createElement("div");
    acciones.className = "acciones";

    const btnEditar = document.createElement("button");
    btnEditar.className = "small secondary";
    btnEditar.textContent = "Editar";
    btnEditar.onclick = (ev) => {
      ev.stopPropagation();
      abrirModalAuto(auto);
    };

    const btnToggle = document.createElement("button");
    btnToggle.className = "small secondary";
    btnToggle.textContent = auto.activo ? "Desactivar" : "Activar";
    btnToggle.onclick = async (ev) => {
      ev.stopPropagation();
      await apiFetch(`/autos/${auto.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activo: !auto.activo }),
      });
      await cargarMiAuto();
    };

    acciones.appendChild(btnEditar);
    acciones.appendChild(btnToggle);
    card.appendChild(acciones);

    card.onclick = () => {
      autoSeleccionadoId = auto.id;
      document.getElementById("filtroAutoSeleccionado").value = String(auto.id);
      renderAutosGrid(autosCache);
      cargarSubtabActual();
    };

    grid.appendChild(card);
  }

  const addCard = document.createElement("div");
  addCard.className = "auto-card-add";
  addCard.textContent = "+ Nuevo vehículo";
  addCard.onclick = () => abrirModalAuto(null);
  grid.appendChild(addCard);
}

function abrirModalAuto(auto) {
  const editando = !!auto;
  abrirModal(
    editando ? `Editar ${auto.nombre}` : "Nuevo vehículo",
    `
      <label>Nombre (el que usas en el tag "auto:")
        <input id="mAutoNombre" value="${editando ? escapeAttr(auto.nombre) : ""}" required></label>
      <label>Marca <input id="mAutoMarca" value="${escapeAttr(auto?.marca)}"></label>
      <label>Modelo <input id="mAutoModelo" value="${escapeAttr(auto?.modelo)}"></label>
      <label>Año <input id="mAutoAnio" type="number" value="${escapeAttr(auto?.anio)}"></label>
      <label>Placas <input id="mAutoPlacas" value="${escapeAttr(auto?.placas)}"></label>
      <div class="modal-acciones">
        <button type="button" class="secondary" id="mAutoCancelar">Cancelar</button>
        <button type="button" id="mAutoGuardar">Guardar</button>
      </div>
    `
  );

  document.getElementById("mAutoCancelar").onclick = cerrarModal;
  document.getElementById("mAutoGuardar").onclick = async () => {
    const nombre = document.getElementById("mAutoNombre").value.trim();
    if (!nombre) {
      alert("El nombre es obligatorio");
      return;
    }
    const anioValor = document.getElementById("mAutoAnio").value;
    const payload = {
      nombre,
      marca: document.getElementById("mAutoMarca").value.trim() || null,
      modelo: document.getElementById("mAutoModelo").value.trim() || null,
      anio: anioValor ? Number(anioValor) : null,
      placas: document.getElementById("mAutoPlacas").value.trim() || null,
    };
    try {
      if (editando) {
        await apiFetch(`/autos/${auto.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/autos", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      cerrarModal();
      await cargarMiAuto();
    } catch (err) {
      alert("Error: " + err.message);
    }
  };
}

function cargarSubtabActual() {
  if (subtabActual === "tareas") return cargarTareasMiAuto();
  return cargarCargasYPagos();
}

async function cargarCargasYPagos() {
  const params = new URLSearchParams({ tipo: "auto", limit: "300" });
  if (autoSeleccionadoId !== "todos") params.set("auto_id", autoSeleccionadoId);
  const datos = await apiFetch(`/gastos?${params.toString()}`);

  const cargas = datos.filter((g) => g.categoria === "gasolina");
  const pagos = datos.filter((g) => g.categoria !== "gasolina");

  const tbodyCargas = limpiarTabla("tablaCargas");
  if (!cargas.length) {
    filaVacia(tbodyCargas, 4);
  } else {
    for (const g of cargas) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(formatoFecha(g.fecha)));
      tr.appendChild(celda(g.comercio));
      tr.appendChild(celda(formatoMoneda(g.monto)));
      tr.appendChild(celda(g.kilometraje));
      tbodyCargas.appendChild(tr);
    }
  }

  const tbodyPagos = limpiarTabla("tablaPagos");
  if (!pagos.length) {
    filaVacia(tbodyPagos, 4);
  } else {
    for (const g of pagos) {
      const tr = document.createElement("tr");
      tr.appendChild(celda(formatoFecha(g.fecha)));
      tr.appendChild(celda(g.categoria));
      tr.appendChild(celda(g.comercio));
      tr.appendChild(celda(formatoMoneda(g.monto)));
      tbodyPagos.appendChild(tr);
    }
  }

  const conKm = cargas
    .filter((g) => g.kilometraje !== null && g.kilometraje !== undefined)
    .sort((a, b) => new Date(a.fecha) - new Date(b.fecha));

  if (chartKmAuto) chartKmAuto.destroy();
  chartKmAuto = new Chart(document.getElementById("chartKmAuto"), {
    type: "line",
    data: {
      labels: conKm.map((g) => formatoFecha(g.fecha)),
      datasets: [
        {
          label: "Kilometraje",
          data: conKm.map((g) => g.kilometraje),
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

async function cargarTareasMiAuto() {
  const estado = document.getElementById("filtroEstadoTarea").value;
  const params = new URLSearchParams();
  if (estado) params.set("estado", estado);
  if (autoSeleccionadoId !== "todos") params.set("auto_id", autoSeleccionadoId);

  const datos = await apiFetch(`/tareas-auto?${params.toString()}`);
  const tbody = limpiarTabla("tablaTareas");
  if (!datos.length) {
    filaVacia(tbody, 7);
    return;
  }

  for (const t of datos) {
    const tr = document.createElement("tr");
    tr.appendChild(celda(t.descripcion));

    const limite = [
      t.fecha_limite ? formatoFecha(t.fecha_limite) : null,
      t.km_limite ? `${t.km_limite} km` : null,
    ]
      .filter(Boolean)
      .join(" / ");
    tr.appendChild(celda(limite));
    tr.appendChild(celda(t.fecha_completada ? formatoFecha(t.fecha_completada) : null));
    tr.appendChild(celda(t.costo !== null && t.costo !== undefined ? formatoMoneda(t.costo) : null));
    tr.appendChild(badgeEstado(t.estado));

    const tdAdj = document.createElement("td");
    const btnAdj = document.createElement("button");
    btnAdj.className = "small secondary";
    btnAdj.textContent = "Ver / agregar";
    btnAdj.onclick = () => abrirModalAdjuntos(t.id, t.descripcion);
    tdAdj.appendChild(btnAdj);
    tr.appendChild(tdAdj);

    const tdAccion = document.createElement("td");
    if (t.estado === "pendiente") {
      const btn = document.createElement("button");
      btn.className = "small";
      btn.textContent = "Completar";
      btn.onclick = () => abrirModalCompletar(t);
      tdAccion.appendChild(btn);
    }
    tr.appendChild(tdAccion);

    tbody.appendChild(tr);
  }
}

function abrirModalCompletar(tarea) {
  abrirModal(
    `Completar: ${tarea.descripcion}`,
    `
      <label>Fecha completada
        <input id="mCompFecha" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
      <label>Costo <input id="mCompCosto" type="number" step="0.01" placeholder="opcional"></label>
      <label>Kilometraje al completar <input id="mCompKm" type="number" placeholder="opcional"></label>
      <div class="modal-acciones">
        <button type="button" class="secondary" id="mCompCancelar">Cancelar</button>
        <button type="button" id="mCompGuardar">Marcar como completada</button>
      </div>
    `
  );

  document.getElementById("mCompCancelar").onclick = cerrarModal;
  document.getElementById("mCompGuardar").onclick = async () => {
    const costo = document.getElementById("mCompCosto").value;
    const km = document.getElementById("mCompKm").value;
    try {
      await apiFetch(`/tareas-auto/${tarea.id}/completar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fecha_completada: document.getElementById("mCompFecha").value || null,
          costo: costo ? Number(costo) : null,
          kilometraje_completado: km ? Number(km) : null,
        }),
      });
      cerrarModal();
      await cargarTareasMiAuto();
    } catch (err) {
      alert("Error: " + err.message);
    }
  };
}

async function abrirModalAdjuntos(tareaId, descripcion) {
  abrirModal(
    `Adjuntos: ${descripcion}`,
    `
      <div class="adjuntos-lista" id="mAdjLista"><span class="vacio">Cargando…</span></div>
      <label>Agregar adjunto
        <input type="file" id="mAdjArchivo" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic"></label>
      <div class="modal-acciones">
        <button type="button" class="secondary" id="mAdjCerrar">Cerrar</button>
        <button type="button" id="mAdjSubir">Subir</button>
      </div>
    `
  );

  document.getElementById("mAdjCerrar").onclick = cerrarModal;
  document.getElementById("mAdjSubir").onclick = async () => {
    const input = document.getElementById("mAdjArchivo");
    if (!input.files[0]) return;
    const fd = new FormData();
    fd.append("file", input.files[0]);
    try {
      await apiFetch(`/tareas-auto/${tareaId}/adjuntos`, { method: "POST", body: fd });
      input.value = "";
      await refrescarListaAdjuntos(tareaId);
    } catch (err) {
      alert("Error al subir: " + err.message);
    }
  };

  await refrescarListaAdjuntos(tareaId);
}

async function refrescarListaAdjuntos(tareaId) {
  const tarea = await apiFetch(`/tareas-auto/${tareaId}`);
  const cont = document.getElementById("mAdjLista");
  if (!cont) return; // el modal se cerró mientras cargaba
  cont.innerHTML = "";
  if (!tarea.adjuntos.length) {
    cont.innerHTML = '<span class="vacio">Sin adjuntos todavía</span>';
    return;
  }
  for (const adj of tarea.adjuntos) {
    const row = document.createElement("div");
    row.className = "adjunto-item";
    const span = document.createElement("span");
    span.textContent = adj.nombre_archivo_original;
    const btn = document.createElement("button");
    btn.className = "small secondary";
    btn.textContent = "Ver";
    btn.onclick = () => verAdjunto(tareaId, adj.id);
    row.appendChild(span);
    row.appendChild(btn);
    cont.appendChild(row);
  }
}

async function verAdjunto(tareaId, adjuntoId) {
  // Se abre la pestaña en blanco de inmediato (dentro del gesto de click del usuario)
  // y se le asigna la URL después: si se espera al fetch antes de abrirla, el navegador
  // puede bloquearla como pop-up porque el gesto de usuario ya "expiró".
  const ventana = window.open("", "_blank");
  try {
    const resp = await fetch(`/tareas-auto/${tareaId}/adjuntos/${adjuntoId}`, {
      headers: { "X-API-Key": getApiKey() },
    });
    if (!resp.ok) throw new Error("respuesta " + resp.status);
    const blob = await resp.blob();
    if (ventana) ventana.location = URL.createObjectURL(blob);
  } catch (err) {
    if (ventana) ventana.close();
    alert("No se pudo abrir el adjunto: " + err.message);
  }
}

// ---------- Ayuda ----------

async function cargarAyuda() {
  const cfg = await apiFetch("/config-publica");

  const elT = document.getElementById("estadoTelegram");
  elT.textContent = cfg.telegram_configurado ? "configurado" : "no configurado";
  elT.className = "tag-estado " + (cfg.telegram_configurado ? "tag-ok" : "tag-no");

  const elE = document.getElementById("estadoEmail");
  elE.textContent = cfg.email_configurado ? "configurado" : "no configurado";
  elE.className = "tag-estado " + (cfg.email_configurado ? "tag-ok" : "tag-no");

  document.getElementById("intervaloEmail").textContent = cfg.email_poll_interval_seconds;
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
    await cargarInicio();
  } catch (err) {
    resultado.className = "error";
    resultado.textContent = "Error al subir: " + err.message;
  }
}

// ---------- Init ----------

function init() {
  const input = document.getElementById("apiKeyInput");
  input.value = getApiKey();
  if (getApiKey()) marcarEstadoKey(true, "guardada");

  document.getElementById("btnGuardarKey").addEventListener("click", () => {
    setApiKey(input.value.trim());
    aplicarVistaDesdeHash();
  });

  for (const btn of document.querySelectorAll(".nav-link")) {
    btn.addEventListener("click", () => {
      window.location.hash = btn.dataset.view;
    });
  }
  window.addEventListener("hashchange", aplicarVistaDesdeHash);

  document.getElementById("formSubir").addEventListener("submit", manejarSubmitSubir);

  document.getElementById("filtroTipo").addEventListener("change", cargarGastos);
  document.getElementById("filtroRecurrente").addEventListener("change", cargarGastos);

  document.getElementById("filtroAutoSeleccionado").addEventListener("change", (ev) => {
    const v = ev.target.value;
    autoSeleccionadoId = v === "todos" ? "todos" : Number(v);
    renderAutosGrid(autosCache);
    cargarSubtabActual();
  });

  document.getElementById("subtabsAuto").addEventListener("click", (ev) => {
    const btn = ev.target.closest(".subtab-btn");
    if (!btn) return;
    subtabActual = btn.dataset.subtab;
    for (const b of document.querySelectorAll(".subtab-btn")) b.classList.toggle("active", b === btn);
    for (const nombre of ["cargas", "pagos", "tareas"]) {
      document.getElementById(`subview-${nombre}`).classList.toggle("hidden", nombre !== subtabActual);
    }
    cargarSubtabActual();
  });

  document.getElementById("filtroEstadoTarea").addEventListener("change", cargarTareasMiAuto);

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
        auto_id: autoSeleccionadoId === "todos" ? null : autoSeleccionadoId,
      }),
    });
    document.getElementById("formTarea").reset();
    await cargarTareasMiAuto();
  });

  document.getElementById("modalCerrar").addEventListener("click", cerrarModal);
  document.getElementById("modalOverlay").addEventListener("click", (ev) => {
    if (ev.target.id === "modalOverlay") cerrarModal();
  });

  aplicarVistaDesdeHash();
}

document.addEventListener("DOMContentLoaded", init);
