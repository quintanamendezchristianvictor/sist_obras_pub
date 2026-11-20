from whitenoise.storage import CompressedManifestStaticFilesStorage


class EstaticosProduccion(CompressedManifestStaticFilesStorage):
    """
    Estáticos comprimidos y con huella en el nombre, para que el navegador los
    guarde en caché sin riesgo de usar una versión antigua (RNF-08). Las librerías
    de static/vendor/ mencionan mapas de depuración (.map) que no se distribuyen:
    esas referencias no deben impedir el despliegue.
    """

    manifest_strict = False
    patterns = tuple(
        (extension, tuple(p for p in patrones if "sourceMappingURL" not in str(p)))
        for extension, patrones in CompressedManifestStaticFilesStorage.patterns
    )
