// Dashboard dinámico (RF-29 a RF-32). Las rutas llegan como atributos data-*
// del formulario de filtros para mantener este archivo fuera de la plantilla.
const formFiltros = document.getElementById('formFiltros');
const datosIniciales = JSON.parse(document.getElementById('datos-graficos-iniciales').textContent);
const COLOR_SEMAFORO = { A_TIEMPO: '#198754', EN_RIESGO: '#ffc107', ATRASADA: '#dc3545' };
const ANCHO_POR_OBRA = 58;  // píxeles por obra: con muchas obras el gráfico se desplaza en lugar de saturarse

// Instancias de Chart.js. No se guardan en window.graficoAvance/graficoEstados
// porque el navegador ya expone ahí los <canvas> con esos mismos id.
let chartAvance = null;
let chartEstados = null;
let chartEvolucion = null;

function construirGraficos(datos) {
    if (chartAvance) chartAvance.destroy();
    if (chartEstados) chartEstados.destroy();
    if (chartEvolucion) chartEvolucion.destroy();

    const lienzoAvance = document.getElementById('graficoAvance');
    lienzoAvance.parentElement.style.minWidth = (datos.etiquetas_obras.length * ANCHO_POR_OBRA) + 'px';

    chartAvance = new Chart(lienzoAvance, {
        type: 'bar',
        data: {
            labels: datos.etiquetas_obras,
            datasets: [
                { label: 'Avance físico programado (%)', data: datos.fisico_programado, backgroundColor: '#90a4ae' },
                // RF-32: cada barra de avance ejecutado toma el color de su semáforo
                { label: 'Avance físico ejecutado (%)', data: datos.fisico_ejecutado,
                  backgroundColor: datos.semaforos.map(s => COLOR_SEMAFORO[s] || '#1f4e78') },
                { label: 'Avance financiero programado (%)', data: datos.financiero_programado, backgroundColor: '#a9c4de' },
                { label: 'Avance financiero ejecutado (%)', data: datos.financiero_ejecutado, backgroundColor: '#1f4e78' },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            scales: { y: { beginAtZero: true, max: 100 }, x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 45 } } }
        }
    });

    chartEstados = new Chart(document.getElementById('graficoEstados'), {
        type: 'doughnut',
        data: {
            labels: datos.estados.etiquetas,
            datasets: [{
                data: datos.estados.valores,
                backgroundColor: ['#1f4e78', '#ffc107', '#198754', '#dc3545'],
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, animation: false }
    });

    chartEvolucion = new Chart(document.getElementById('graficoEvolucion'), {
        type: 'line',
        data: {
            labels: datos.evolucion.etiquetas,
            datasets: [
                { label: 'Físico programado (%)', data: datos.evolucion.programado, borderColor: '#90a4ae', backgroundColor: '#90a4ae', borderDash: [6, 4], tension: 0.2 },
                { label: 'Físico ejecutado (%)', data: datos.evolucion.ejecutado, borderColor: '#1f4e78', backgroundColor: '#1f4e78', tension: 0.2 },
                { label: 'Financiero programado (%)', data: datos.evolucion.financiero_programado, borderColor: '#e0a96d', backgroundColor: '#e0a96d', borderDash: [6, 4], tension: 0.2 },
                { label: 'Financiero ejecutado (%)', data: datos.evolucion.financiero_ejecutado, borderColor: '#c8741a', backgroundColor: '#c8741a', tension: 0.2 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            scales: { y: { beginAtZero: true, max: 100 } }
        }
    });
}

function actualizarKPIs(datos) {
    document.getElementById('kpiTotal').textContent = datos.total_obras;
    document.getElementById('kpiFisico').textContent = datos.promedio_fisico_ejecutado + '%';
    document.getElementById('kpiFisicoProg').textContent = datos.promedio_fisico_programado;
    document.getElementById('kpiFinanciero').textContent = datos.promedio_financiero_ejecutado + '%';
    document.getElementById('kpiFinancieroProg').textContent = datos.promedio_financiero_programado;
    document.getElementById('kpiRiesgo').textContent = datos.total_en_riesgo;
    document.getElementById('estadoEjecucion').textContent = datos.conteo_estados.EN_EJECUCION;
    document.getElementById('estadoParalizada').textContent = datos.conteo_estados.PARALIZADA;
    document.getElementById('estadoConcluida').textContent = datos.conteo_estados.CONCLUIDA;
    document.getElementById('estadoRetraso').textContent = datos.conteo_estados.CON_RETRASO;
}

// Crea una celda con texto plano: los datos nunca se interpretan como HTML (evita XSS).
function celda(texto) {
    const td = document.createElement('td');
    td.textContent = texto;
    return td;
}

function actualizarTablaRiesgo(datos) {
    const tbody = document.querySelector('#tablaRiesgo tbody');
    tbody.replaceChildren();
    if (!datos.obras_en_riesgo.length) {
        const td = celda('No hay obras en riesgo con los filtros actuales.');
        td.colSpan = 7;
        td.className = 'text-center text-muted py-4';
        const tr = document.createElement('tr');
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }
    datos.obras_en_riesgo.forEach(o => {
        const tr = document.createElement('tr');
        tr.append(celda(o.codigo), celda(o.nombre), celda(o.estado),
                  celda(o.avance_fisico + '%'), celda(o.desviacion + ' pp'));
        const tdSemaforo = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = 'badge badge-semaforo-' + o.semaforo;
        badge.textContent = o.semaforo_display;
        tdSemaforo.appendChild(badge);
        const tdVer = document.createElement('td');
        const enlace = document.createElement('a');
        enlace.href = '/obras/' + encodeURIComponent(o.id) + '/';
        enlace.className = 'btn btn-sm btn-outline-primary';
        enlace.textContent = 'Ver';
        tdVer.appendChild(enlace);
        tr.append(tdSemaforo, tdVer);
        tbody.appendChild(tr);
    });
}

function parametrosFiltro() {
    return new URLSearchParams(new FormData(formFiltros)).toString();
}

function marcarActualizacion() {
    document.getElementById('ultimaActualizacion').textContent =
        'Actualizado: ' + new Date().toLocaleTimeString('es-PE');
}

// Render inicial con los datos ya calculados en el servidor (evita doble consulta al cargar)
let firmaActual = JSON.parse(document.getElementById('firma-inicial').textContent);
construirGraficos(datosIniciales);
marcarActualizacion();

// RF-31: refresco dinámico de indicadores y gráficos sin recargar la página completa.
function refrescarDashboard() {
    const params = parametrosFiltro();
    // Los botones PDF/Excel exportan siempre con los filtros vigentes
    document.getElementById('btnPdf').href = formFiltros.dataset.urlPdf + '?' + params;
    document.getElementById('btnExcel').href = formFiltros.dataset.urlExcel + '?' + params;
    fetch(formFiltros.dataset.urlDatos + '?' + params)
        .then(r => r.json())
        .then(datos => {
            firmaActual = datos.firma;
            actualizarKPIs(datos);
            actualizarTablaRiesgo(datos);
            construirGraficos(datos.graficos);
            marcarActualizacion();
        });
}

['filtroObra', 'filtroEstado', 'filtroUnidad', 'filtroPeriodo'].forEach(id => {
    document.getElementById(id).addEventListener('change', refrescarDashboard);
});
formFiltros.addEventListener('submit', function (e) {
    e.preventDefault();
    refrescarDashboard();
});

// RF-31: cada 4 s se consulta una "firma" mínima de los datos, para que el panel refleje
// lo registrado en menos de 5 s (RNF-06); solo se vuelve a descargar cuando alguien
// registró información nueva (RNF-08).
setInterval(function () {
    if (document.hidden) return;
    fetch(formFiltros.dataset.urlFirma)
        .then(r => r.json())
        .then(d => { if (d.firma !== firmaActual) refrescarDashboard(); })
        .catch(() => {});  // sin conexión: se reintenta en el siguiente ciclo
}, 4000);
