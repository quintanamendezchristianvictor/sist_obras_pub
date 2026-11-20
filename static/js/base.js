// RNF-10: confirmación antes de ejecutar operaciones críticas. Basta con
// agregar data-confirmar="mensaje" al <form> que se quiera proteger.
document.querySelectorAll('form[data-confirmar]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
        if (!window.confirm(form.dataset.confirmar)) e.preventDefault();
    });
});

// RNF-19: evita registros duplicados por pulsar dos veces "Guardar" en una
// conexión lenta. Se ejecuta después de la confirmación anterior.
document.querySelectorAll('form[method="post"]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
        if (e.defaultPrevented) return;
        form.querySelectorAll('button[type="submit"]').forEach(function (b) { b.disabled = true; });
    });
});
// Al volver con el botón "Atrás", el navegador restaura la página tal como estaba
window.addEventListener('pageshow', function () {
    document.querySelectorAll('form[method="post"] button[type="submit"]').forEach(function (b) { b.disabled = false; });
});

// RNF-10: resalta en rojo los campos con error para ubicarlos rápidamente.
(function () {
    const nodo = document.getElementById('campos-con-error');
    if (!nodo) return;
    JSON.parse(nodo.textContent).forEach(function (nombre) {
        document.querySelectorAll('[name="' + nombre + '"]').forEach(function (el) { el.classList.add('is-invalid'); });
    });
})();
