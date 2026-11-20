"""
Pruebas unitarias del dashboard dinámico (RF-29 a RF-32).
"""

import io
from datetime import date, timedelta
from decimal import Decimal

import openpyxl
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from avances.models import AvanceObra
from core.constants import ROL_ALTA_DIRECCION, ROL_SUPERVISOR
from obras.models import FichaInfobras, Obra, ParalizacionObra
from usuarios.models import Usuario

from .services import construir_datos_dashboard


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(
            codigo="OB-TEST-003",
            nombre="Obra para dashboard",
            meta_fisica="1.0 km",
            plazo_ejecucion_dias=100,
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin_programada=date.today() + timedelta(days=70),
            presupuesto_asignado=Decimal("50000.00"),
        )
        AvanceObra.objects.create(
            obra=self.obra, periodo=date.today().replace(day=1),
            avance_fisico_programado_acum=Decimal("80"),
            avance_fisico_ejecutado_acum=Decimal("50"),
            avance_financiero_programado_acum=Decimal("80"),
            avance_financiero_ejecutado_acum=Decimal("50"),
        )

    def _request(self, usuario):
        request = RequestFactory().get("/reportes/")
        request.user = usuario
        return request

    def test_dashboard_detecta_obra_en_riesgo(self):
        direccion = Usuario.objects.create_user(username="direccion_s", password="Clave12345", rol=ROL_ALTA_DIRECCION)
        datos = construir_datos_dashboard(self._request(direccion))
        self.assertEqual(datos["total_obras"], 1)
        self.assertEqual(datos["total_en_riesgo"], 1)
        self.assertEqual(datos["obras_en_riesgo"][0]["codigo"], "OB-TEST-003")

    def test_dashboard_supervisor_solo_ve_sus_obras(self):
        # RF-04: el dashboard no debe listar obras que el supervisor no puede abrir
        supervisor = Usuario.objects.create_user(username="supervisor_s", password="Clave12345", rol=ROL_SUPERVISOR)
        datos = construir_datos_dashboard(self._request(supervisor))
        self.assertEqual(datos["total_obras"], 0)

        self.obra.supervisor = supervisor
        self.obra.save()
        datos = construir_datos_dashboard(self._request(supervisor))
        self.assertEqual(datos["total_obras"], 1)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="direccion_t", password="Clave12345", rol=ROL_ALTA_DIRECCION
        )

    def test_dashboard_accesible_para_alta_direccion(self):
        self.client.login(username="direccion_t", password="Clave12345")
        response = self.client.get(reverse("reportes:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_endpoint_json_devuelve_datos_validos(self):
        self.client.login(username="direccion_t", password="Clave12345")
        response = self.client.get(reverse("reportes:dashboard_data"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")


class DashboardPeriodoYEficienciaTests(TestCase):
    """RF-30 (filtro por periodo), RF-31 (firma de cambios) y RNF-04/RNF-06 (consultas acotadas)."""

    def setUp(self):
        self.direccion = Usuario.objects.create_user(username="dir_ef", password="Clave12345", rol=ROL_ALTA_DIRECCION)
        self.obra = self._crear_obra("OB-EF-000")
        # Enero: a tiempo; marzo: atrasada
        for periodo, programado, ejecutado in ((date(2026, 1, 1), 20, 20), (date(2026, 3, 1), 60, 30)):
            AvanceObra.objects.create(
                obra=self.obra, periodo=periodo, avance_fisico_programado_acum=Decimal(programado),
                avance_fisico_ejecutado_acum=Decimal(ejecutado), avance_financiero_programado_acum=Decimal(programado),
                avance_financiero_ejecutado_acum=Decimal(ejecutado),
            )

    def _crear_obra(self, codigo):
        return Obra.objects.create(
            codigo=codigo, nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=300,
            fecha_inicio=date(2025, 12, 1), fecha_fin_programada=date(2026, 9, 27),
            presupuesto_asignado=Decimal("50000.00"),
        )

    def _datos(self, consulta=""):
        request = RequestFactory().get("/reportes/" + consulta)
        request.user = self.direccion
        return construir_datos_dashboard(request)

    def test_filtro_por_periodo_usa_el_avance_vigente_a_esa_fecha(self):
        self.assertEqual(self._datos("?periodo=2026-02")["total_en_riesgo"], 0)
        self.assertEqual(self._datos("?periodo=2026-02")["promedio_fisico_ejecutado"], 20)
        self.assertEqual(self._datos()["total_en_riesgo"], 1)
        self.assertEqual(self._datos()["graficos"]["evolucion"]["etiquetas"], ["01/2026", "03/2026"])

    def test_evolucion_incluye_el_avance_financiero_programado_y_ejecutado(self):
        evolucion = self._datos()["graficos"]["evolucion"]
        self.assertEqual(evolucion["financiero_programado"], [20, 60])
        self.assertEqual(evolucion["financiero_ejecutado"], [20, 30])

    def test_numero_de_consultas_no_depende_del_numero_de_obras(self):
        self._datos()  # la primera llamada crea la configuración del sistema
        with CaptureQueriesContext(connection) as con_una:
            self._datos()
        for i in range(1, 15):
            obra = self._crear_obra(f"OB-EF-{i:03d}")
            AvanceObra.objects.create(
                obra=obra, periodo=date(2026, 1, 1), avance_fisico_programado_acum=Decimal(10),
                avance_fisico_ejecutado_acum=Decimal(10), avance_financiero_programado_acum=Decimal(10),
                avance_financiero_ejecutado_acum=Decimal(10),
            )
        with CaptureQueriesContext(connection) as con_quince:
            datos = self._datos()
        self.assertEqual(datos["total_obras"], 15)
        self.assertEqual(len(con_una), len(con_quince))

    def test_la_firma_cambia_al_registrar_informacion(self):
        from core.models import Bitacora

        firma = self._datos()["firma"]
        Bitacora.objects.create(usuario=self.direccion, accion="CREAR/ACTUALIZAR", modulo="avances")
        self.client.force_login(self.direccion)
        respuesta = self.client.get(reverse("reportes:dashboard_firma"))
        self.assertNotEqual(respuesta.json()["firma"], firma)

    def test_reportes_pdf_y_excel_con_filtro_de_periodo(self):
        self.client.force_login(self.direccion)
        for nombre in ("reportes:consolidado_pdf", "reportes:consolidado_excel"):
            respuesta = self.client.get(reverse(nombre), {"periodo": "2026-02"})
            self.assertEqual(respuesta.status_code, 200, nombre)


class ReporteInfobrasTests(TestCase):
    """RF-28: el libro Excel contiene las secciones de información que exige INFOBRAS."""

    def setUp(self):
        self.direccion = Usuario.objects.create_user(username="dir_inf", password="Clave12345", rol=ROL_ALTA_DIRECCION)
        self.obra = Obra.objects.create(
            codigo="OB-X", nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=90,
            fecha_inicio=date(2026, 1, 1), fecha_fin_programada=date(2026, 4, 1), presupuesto_asignado=Decimal("1000"),
        )
        FichaInfobras.objects.create(obra=self.obra, contrato_numero="C-9", naturaleza="MEJORAMIENTO", liquidacion_resolucion="RGM-1")
        ParalizacionObra.objects.create(obra=self.obra, fecha_inicio=date(2026, 2, 1), motivo="Lluvias")
        AvanceObra.objects.create(
            obra=self.obra, periodo=date(2026, 1, 1), avance_fisico_programado_acum=10, avance_fisico_ejecutado_acum=10,
            avance_financiero_programado_acum=10, avance_financiero_ejecutado_acum=10,
        )
        self.client.force_login(self.direccion)

    def _libro(self):
        respuesta = self.client.get(reverse("reportes:consolidado_excel"))
        return openpyxl.load_workbook(io.BytesIO(respuesta.content))

    def test_hojas_y_datos(self):
        libro = self._libro()
        self.assertEqual(libro.sheetnames, [
            "Reporte consolidado INFOBRAS", "Datos generales y contrato", "Avances mensuales", "Cronograma",
            "Modificaciones", "Paralizaciones", "Cierre de obra",
        ])
        self.assertEqual(libro["Datos generales y contrato"]["K2"].value, "C-9")
        self.assertEqual(libro["Paralizaciones"]["D2"].value, "Lluvias")
        self.assertEqual(libro["Avances mensuales"]["B2"].value, "01/2026")
        self.assertEqual(libro["Cierre de obra"]["F2"].value, "RGM-1")

    def test_consultas_constantes(self):
        self.client.get(reverse("reportes:consolidado_excel"))
        with CaptureQueriesContext(connection) as con_una:
            self.client.get(reverse("reportes:consolidado_excel"))
        for i in range(5):
            Obra.objects.create(
                codigo=f"OB-X{i}", nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=90,
                fecha_inicio=date(2026, 1, 1), fecha_fin_programada=date(2026, 4, 1), presupuesto_asignado=Decimal("1000"),
            )
        with CaptureQueriesContext(connection) as con_seis:
            self.client.get(reverse("reportes:consolidado_excel"))
        self.assertEqual(len(con_seis), len(con_una))
