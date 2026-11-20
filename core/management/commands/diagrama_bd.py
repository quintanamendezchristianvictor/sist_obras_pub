"""
Genera el diagrama entidad-relación de la base de datos en formato Mermaid, a
partir de los modelos, para que la documentación no se desactualice (RNF-22).

    python manage.py diagrama_bd                  # docs/diagrama_bd.mmd
    python manage.py diagrama_bd --resumen        # solo llaves y relaciones
    python manage.py diagrama_bd --apps obras usuarios --salida docs/x.mmd   # un módulo
"""

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, models

APPS_DEL_SISTEMA = ["usuarios", "core", "obras", "avances", "valorizaciones", "calendario", "documentos"]
_COLUMNAS_OMITIDAS = {"usuarios_usuario": {"password", "last_login", "is_superuser", "is_staff", "date_joined"}}


def _tipo(campo):
    if isinstance(campo, models.ForeignKey | models.OneToOneField):
        return "bigint"
    if isinstance(campo, models.DecimalField):
        return f"decimal_{campo.max_digits}_{campo.decimal_places}"
    if isinstance(campo, models.CharField):
        return f"varchar_{campo.max_length}"
    return campo.db_type(connection=connection).split("(")[0].split(" ")[0]


def _marcas(campo, unicos):
    marcas = []
    if campo.primary_key:
        marcas.append("PK")
    if campo.is_relation:
        marcas.append("FK")
    if (campo.unique and not campo.primary_key) or campo.name in unicos:
        marcas.append("UK")
    return ", ".join(marcas)


class Command(BaseCommand):
    help = "Genera el diagrama entidad-relación de la base de datos en formato Mermaid."

    def add_arguments(self, parser):
        parser.add_argument("--resumen", action="store_true", help="Muestra solo llaves primarias y foráneas.")
        parser.add_argument("--apps", nargs="+", default=APPS_DEL_SISTEMA, help="Módulos que se muestran con todas sus columnas.")
        parser.add_argument("--salida", default=None, help="Archivo de salida (por defecto, en docs/).")

    def handle(self, *args, **options):
        principales = [m for etiqueta in options["apps"] for m in apps.get_app_config(etiqueta).get_models()]
        # Las tablas de otros módulos a las que se hace referencia aparecen solo con su llave primaria
        referidas = []
        for modelo in principales:
            for campo in modelo._meta.concrete_fields:
                destino = campo.related_model if campo.is_relation else None
                if destino and destino not in principales and destino not in referidas and destino._meta.app_label in APPS_DEL_SISTEMA:
                    referidas.append(destino)

        lineas = ["erDiagram"]
        for modelo in principales:
            lineas.extend(self._entidad(modelo, options["resumen"]))
        for modelo in referidas:
            lineas.extend([f"    {modelo._meta.db_table} {{", "        bigint id PK", "    }"])
        lineas.extend(self._relaciones(principales, principales + referidas))

        nombre = "diagrama_bd_resumen.mmd" if options["resumen"] else "diagrama_bd.mmd"
        salida = Path(options["salida"]) if options["salida"] else Path(settings.BASE_DIR) / "docs" / nombre
        salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Diagrama con {len(principales)} tablas: {salida}"))

    def _entidad(self, modelo, resumen):
        tabla = modelo._meta.db_table
        unicos = {nombre for grupo in modelo._meta.unique_together for nombre in grupo}
        lineas = [f"    {tabla} {{"]
        for campo in modelo._meta.concrete_fields:
            if campo.name in _COLUMNAS_OMITIDAS.get(tabla, ()) or (resumen and not (campo.primary_key or campo.is_relation)):
                continue
            lineas.append(f"        {_tipo(campo)} {campo.column} {_marcas(campo, unicos)}".rstrip())
        lineas.append("    }")
        return lineas

    def _relaciones(self, principales, visibles):
        lineas = []
        for modelo in principales:
            for campo in modelo._meta.concrete_fields:
                if not campo.is_relation or campo.related_model not in visibles:
                    continue
                if isinstance(campo, models.OneToOneField):
                    simbolo = "||--o|"
                elif campo.null:
                    simbolo = "|o--o{"
                else:
                    simbolo = "||--o{"
                lineas.append(f'    {campo.related_model._meta.db_table} {simbolo} {modelo._meta.db_table} : "{campo.name}"')
        return lineas
