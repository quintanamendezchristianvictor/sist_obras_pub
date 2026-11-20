"""
Backend de base de datos para el MySQL/MariaDB incluido en XAMPP.

Django 5.2 exige MariaDB 10.5 o superior, pero XAMPP para Windows sigue
distribuyendo MariaDB 10.4. Este backend reutiliza íntegramente el backend
oficial de MySQL de Django y solo rebaja la versión mínima aceptada a 10.4.
Django ya ajusta según la versión detectada casi todas las funcionalidades;
la excepción es INSERT ... RETURNING (solo existe desde MariaDB 10.5), que
aquí se desactiva para que el id del registro nuevo se obtenga como en MySQL.
"""

import operator

from django.db.backends.mysql import base, features
from django.utils.functional import cached_property


class DatabaseFeatures(features.DatabaseFeatures):
    @property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:
            return (10, 4)
        return super().minimum_database_version

    @cached_property
    def can_return_columns_from_insert(self):
        return self.connection.mysql_is_mariadb and self.connection.mysql_version >= (10, 5)

    can_return_rows_from_bulk_insert = property(
        operator.attrgetter("can_return_columns_from_insert")
    )


class DatabaseWrapper(base.DatabaseWrapper):
    features_class = DatabaseFeatures
