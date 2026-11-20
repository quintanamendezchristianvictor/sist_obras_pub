"""
Pruebas unitarias del módulo de obras.

Estas pruebas verifican, entre otras cosas, el cálculo automático de
indicadores (RF-13, RF-14, RF-23) y el control de acceso por rol (RF-04),
y sirven como parte de la verificación de corrección funcional exigida por
RNF-02 (corrección funcional) de la especificación de requisitos.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from calendario.models import ESTADO_APROBADO, TIPO_ADICIONAL, AdicionalDeductivo
from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from usuarios.models import Usuario

from .forms import ExpedienteTecnicoForm, ObraForm
from .models import ExpedienteTecnico, FichaInfobras, Obra


class ObraModelTests(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(
            codigo="OB-TEST-001",
            nombre="Obra de prueba",
            meta_fisica="1.0 km",
            plazo_ejecucion_dias=100,
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin_programada=date.today() + timedelta(days=70),
            presupuesto_asignado=Decimal("100000.00"),
        )

    def test_provincia_predeterminada_es_la_mar(self):
        self.assertEqual(self.obra.provincia, "La Mar")

    def test_presupuesto_vigente_sin_modificaciones(self):
        self.assertEqual(self.obra.presupuesto_vigente, Decimal("100000.00"))

    def test_presupuesto_vigente_con_adicional_aprobado(self):
        AdicionalDeductivo.objects.create(
            obra=self.obra, tipo=TIPO_ADICIONAL, numero=1,
            monto=Decimal("10000.00"), sustento="Mayores metrados",
            estado=ESTADO_APROBADO, fecha_solicitud=date.today(),
        )
        self.assertEqual(self.obra.presupuesto_vigente, Decimal("110000.00"))

    def test_plazo_vigente_sin_ampliaciones(self):
        self.assertEqual(self.obra.plazo_vigente_dias, 100)


class ObraAccesoPorRolTests(TestCase):
    """Verifica RF-04: el acceso a crear/editar obras está restringido por rol."""

    def setUp(self):
        self.admin = Usuario.objects.create_user(username="admin_t", password="Clave12345", rol=ROL_ADMIN)
        self.residente = Usuario.objects.create_user(username="residente_t", password="Clave12345", rol=ROL_RESIDENTE)

    def test_residente_no_puede_crear_obra(self):
        self.client.login(username="residente_t", password="Clave12345")
        response = self.client.get(reverse("obras:crear"))
        self.assertEqual(response.status_code, 403)

    def test_admin_puede_crear_obra(self):
        self.client.login(username="admin_t", password="Clave12345")
        response = self.client.get(reverse("obras:crear"))
        self.assertEqual(response.status_code, 200)

    def test_anonimo_redirige_a_login(self):
        response = self.client.get(reverse("obras:lista"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("usuarios:login"), response.url)


class ObraAjenaTests(TestCase):
    """Verifica RF-04: el residente no accede a los módulos de una obra que no tiene asignada."""

    def setUp(self):
        self.residente = Usuario.objects.create_user(username="residente_a", password="Clave12345", rol=ROL_RESIDENTE)
        datos = dict(
            meta_fisica="1.0 km", plazo_ejecucion_dias=100,
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin_programada=date.today() + timedelta(days=70),
            presupuesto_asignado=Decimal("100000.00"),
        )
        self.propia = Obra.objects.create(codigo="OB-PROPIA", nombre="Obra propia", residente=self.residente, **datos)
        self.ajena = Obra.objects.create(codigo="OB-AJENA", nombre="Obra ajena", **datos)
        self.client.login(username="residente_a", password="Clave12345")

    def test_modulos_de_obra_propia_accesibles(self):
        for nombre in ("avances:lista", "avances:crear", "valorizaciones:lista", "documentos:lista"):
            response = self.client.get(reverse(nombre, args=[self.propia.pk]))
            self.assertEqual(response.status_code, 200, nombre)

    def test_modulos_de_obra_ajena_no_accesibles(self):
        for nombre in ("avances:lista", "avances:crear", "valorizaciones:lista", "valorizaciones:crear",
                       "calendario:lista", "documentos:lista"):
            response = self.client.get(reverse(nombre, args=[self.ajena.pk]))
            self.assertEqual(response.status_code, 404, nombre)

class PermisosPorActorTests(TestCase):
    """
    Verifica RF-03/RF-04 frente a los actores del numeral 3.2 de la
    especificación: cada rol solo accede a los registros que le corresponden.
    """

    # pantalla de registro -> roles que pueden abrirla
    MATRIZ = {
        "obras:crear": {ROL_ADMIN},
        "avances:crear": {ROL_ADMIN, ROL_RESIDENTE},
        "valorizaciones:crear": {ROL_ADMIN, ROL_RESIDENTE},
        "valorizaciones:informe_crear": {ROL_ADMIN, ROL_RESIDENTE, ROL_SUPERVISOR},
        "calendario:crear": {ROL_ADMIN},
        "calendario:ampliacion_crear": {ROL_ADMIN},
        "calendario:adicional_crear": {ROL_ADMIN},
        "documentos:crear": {ROL_ADMIN, ROL_APOYO},
    }

    def setUp(self):
        self.usuarios = {
            rol: Usuario.objects.create_user(username=f"u_{rol.lower()}", password="Clave12345", rol=rol)
            for rol in (ROL_ADMIN, ROL_RESIDENTE, ROL_SUPERVISOR, ROL_APOYO, ROL_ALTA_DIRECCION)
        }
        self.obra = Obra.objects.create(
            codigo="OB-MATRIZ", nombre="Obra matriz", meta_fisica="1.0 km", plazo_ejecucion_dias=100,
            fecha_inicio=date.today(), fecha_fin_programada=date.today() + timedelta(days=100),
            presupuesto_asignado=Decimal("100000.00"),
            residente=self.usuarios[ROL_RESIDENTE], supervisor=self.usuarios[ROL_SUPERVISOR],
        )

    def test_matriz_de_permisos(self):
        for nombre, roles in self.MATRIZ.items():
            args = [] if nombre == "obras:crear" else [self.obra.pk]
            for rol, usuario in self.usuarios.items():
                self.client.force_login(usuario)
                esperado = 200 if rol in roles else 403
                response = self.client.get(reverse(nombre, args=args))
                self.assertEqual(response.status_code, esperado, f"{rol} en {nombre}")

class FechasEnFormulariosTests(TestCase):
    """Un campo de fecha del navegador solo acepta el formato ISO: con otro formato aparece vacío al editar."""

    def test_formularios_de_edicion_conservan_las_fechas_registradas(self):
        obra = Obra.objects.create(
            codigo="OB-FEC", nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=90,
            fecha_inicio=date(2026, 8, 1), fecha_fin_programada=date(2026, 10, 30), presupuesto_asignado=Decimal("1000"),
        )
        formulario = ObraForm(instance=obra)
        self.assertIn('value="2026-08-01"', str(formulario["fecha_inicio"]))
        self.assertIn('value="2026-10-30"', str(formulario["fecha_fin_programada"]))
        expediente = ExpedienteTecnico(obra=obra, numero_expediente="1", fecha_aprobacion=date(2026, 5, 15), monto_expediente=1)
        self.assertIn('value="2026-05-15"', str(ExpedienteTecnicoForm(instance=expediente)["fecha_aprobacion"]))


class ListadoEficienteTests(TestCase):
    """RNF-04: el número de consultas del listado no depende del número de obras."""

    def _crear(self, codigo):
        return Obra.objects.create(
            codigo=codigo, nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=90, unidad_organica="Unidad A",
            fecha_inicio=date(2026, 1, 1), fecha_fin_programada=date(2026, 4, 1), presupuesto_asignado=Decimal("1000"),
        )

    @override_settings(CONFIGURACION_CACHE_SEGUNDOS=60)
    def test_consultas_constantes_y_filtro_por_unidad(self):
        cache.clear()
        admin = Usuario.objects.create_user(username="adm_lista", password="Clave12345", rol=ROL_ADMIN)
        self.client.force_login(admin)
        self._crear("OB-L0")
        self.client.get(reverse("obras:lista"))
        with CaptureQueriesContext(connection) as con_una:
            self.client.get(reverse("obras:lista"))
        for i in range(1, 10):
            self._crear(f"OB-L{i}")
        with CaptureQueriesContext(connection) as con_diez:
            respuesta = self.client.get(reverse("obras:lista"))
        self.assertEqual(len(con_diez), len(con_una))
        self.assertEqual(list(respuesta.context["unidades"]), ["Unidad A"])


class FichaInfobrasTests(TestCase):
    """RF-28: datos que exige INFOBRAS."""

    def setUp(self):
        self.admin = Usuario.objects.create_user(username="adm_inf", password="Clave12345", rol=ROL_ADMIN)
        self.obra = Obra.objects.create(
            codigo="OB-INF", nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=90,
            fecha_inicio=date(2026, 1, 1), fecha_fin_programada=date(2026, 4, 1), presupuesto_asignado=Decimal("1000"),
        )
        self.url = reverse("obras:ficha_infobras", args=[self.obra.pk])
        self.client.force_login(self.admin)
        self.formset = {"paralizaciones-TOTAL_FORMS": 1, "paralizaciones-INITIAL_FORMS": 0}

    def test_abrir_el_formulario_no_crea_registros(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertFalse(FichaInfobras.objects.exists())

    def test_guarda_datos_y_paralizaciones(self):
        datos = {**self.formset, "contrato_numero": "C-1", "latitud": "-12.5", "longitud": "-73.9",
                 "paralizaciones-0-fecha_inicio": "2026-02-01", "paralizaciones-0-motivo": "Lluvias"}
        self.assertEqual(self.client.post(self.url, datos).status_code, 302)
        self.assertEqual(self.obra.ficha_infobras.contrato_numero, "C-1")
        self.assertEqual(self.obra.paralizaciones.get().motivo, "Lluvias")

    def test_valida_coordenadas_y_fechas(self):
        datos = {**self.formset, "latitud": "-12.5", "recepcion_fecha": "2025-01-01", "paralizaciones-TOTAL_FORMS": 0}
        respuesta = self.client.post(self.url, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("longitud", respuesta.context["form"].errors)
        self.assertIn("recepcion_fecha", respuesta.context["form"].errors)

    def test_solo_el_administrador_accede(self):
        residente = Usuario.objects.create_user(username="res_inf", password="Clave12345", rol=ROL_RESIDENTE)
        self.client.force_login(residente)
        self.assertEqual(self.client.get(self.url).status_code, 403)
