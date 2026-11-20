"""
Pruebas del control del calendario de ejecución y de las modificaciones
contractuales (RF-20 a RF-23): flujo solicitud -> aprobación/rechazo y
recálculo automático del plazo y del presupuesto vigentes.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from avances.models import AvanceObra
from core.constants import ROL_ADMIN, ROL_SUPERVISOR
from obras.models import Obra
from usuarios.models import Usuario

from .forms import CalendarioEjecucionForm
from .models import (
    ESTADO_APROBADA,
    ESTADO_APROBADO,
    ESTADO_RECHAZADA,
    ESTADO_SOLICITADA,
    ESTADO_SOLICITADO,
    TIPO_ADICIONAL,
    TIPO_DEDUCTIVO,
    AdicionalDeductivo,
    AmpliacionPlazo,
)


class ModificacionesBase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username="adm_cal", password="Clave12345", rol=ROL_ADMIN)
        inicio = date.today() - timedelta(days=60)
        self.obra = Obra.objects.create(
            codigo="OB-CAL-01", nombre="Obra calendario", meta_fisica="1 km", plazo_ejecucion_dias=120,
            fecha_inicio=inicio, fecha_fin_programada=inicio + timedelta(days=120),
            presupuesto_asignado=Decimal("200000.00"),
        )
        self.client.force_login(self.admin)


class AmpliacionPlazoTests(ModificacionesBase):
    def _solicitar(self, dias=30):
        return self.client.post(reverse("calendario:ampliacion_crear", args=[self.obra.pk]), {
            "numero": 1, "fecha_solicitud": date.today().isoformat(), "motivo": "Lluvias intensas",
            "dias_solicitados": dias,
        })

    def test_la_solicitud_no_modifica_el_plazo_hasta_aprobarse(self):
        self.assertEqual(self._solicitar().status_code, 302)
        ampliacion = AmpliacionPlazo.objects.get()
        self.assertEqual(ampliacion.estado, ESTADO_SOLICITADA)
        self.assertEqual(self.obra.plazo_vigente_dias, 120)

    def test_aprobar_recalcula_plazo_y_fecha_fin(self):
        self._solicitar(30)
        ampliacion = AmpliacionPlazo.objects.get()
        respuesta = self.client.post(reverse("calendario:ampliacion_resolver", args=[self.obra.pk, ampliacion.pk]), {
            "estado": ESTADO_APROBADA, "dias_otorgados": 20, "fecha_aprobacion": date.today().isoformat(),
            "resolucion": "R.A. N° 001-2026-MDSR",
        })
        self.assertEqual(respuesta.status_code, 302)
        obra = Obra.objects.get(pk=self.obra.pk)
        self.assertEqual(obra.plazo_vigente_dias, 140)
        self.assertEqual(obra.fecha_fin_vigente, obra.fecha_fin_programada + timedelta(days=20))

    def test_no_se_otorgan_mas_dias_que_los_solicitados(self):
        self._solicitar(10)
        ampliacion = AmpliacionPlazo.objects.get()
        respuesta = self.client.post(reverse("calendario:ampliacion_resolver", args=[self.obra.pk, ampliacion.pk]), {
            "estado": ESTADO_APROBADA, "dias_otorgados": 15, "fecha_aprobacion": date.today().isoformat(),
            "resolucion": "R.A. 2",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Obra.objects.get(pk=self.obra.pk).plazo_vigente_dias, 120)

    def test_rechazo_no_amplia_y_no_puede_resolverse_dos_veces(self):
        self._solicitar(30)
        ampliacion = AmpliacionPlazo.objects.get()
        url = reverse("calendario:ampliacion_resolver", args=[self.obra.pk, ampliacion.pk])
        self.client.post(url, {"estado": ESTADO_RECHAZADA, "dias_otorgados": 30,
                               "fecha_aprobacion": date.today().isoformat(), "resolucion": "R.A. 3"})
        ampliacion.refresh_from_db()
        self.assertEqual(ampliacion.estado, ESTADO_RECHAZADA)
        self.assertEqual(ampliacion.dias_otorgados, 0)
        self.assertEqual(self.obra.plazo_vigente_dias, 120)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_solo_el_administrador_resuelve(self):
        self._solicitar()
        ampliacion = AmpliacionPlazo.objects.get()
        supervisor = Usuario.objects.create_user(username="sup_cal", password="Clave12345", rol=ROL_SUPERVISOR)
        self.obra.supervisor = supervisor
        self.obra.save()
        self.client.force_login(supervisor)
        url = reverse("calendario:ampliacion_resolver", args=[self.obra.pk, ampliacion.pk])
        self.assertEqual(self.client.get(url).status_code, 403)


class AdicionalDeductivoTests(ModificacionesBase):
    def _crear(self, tipo, monto):
        return AdicionalDeductivo.objects.create(
            obra=self.obra, tipo=tipo, numero=1, monto=Decimal(monto), sustento="Sustento",
            estado=ESTADO_SOLICITADO, fecha_solicitud=date.today(),
        )

    def _resolver(self, item, estado="APROBADO"):
        return self.client.post(reverse("calendario:adicional_resolver", args=[self.obra.pk, item.pk]), {
            "estado": estado, "fecha_aprobacion": date.today().isoformat(), "resolucion": "R.A. 10",
        })

    def test_aprobar_adicional_y_deductivo_recalcula_presupuesto(self):
        self._resolver(self._crear(TIPO_ADICIONAL, "30000"))
        self._resolver(self._crear(TIPO_DEDUCTIVO, "5000"))
        self.assertEqual(Obra.objects.get(pk=self.obra.pk).presupuesto_vigente, Decimal("225000.00"))

    def test_deductivo_no_puede_superar_presupuesto_vigente(self):
        deductivo = self._crear(TIPO_DEDUCTIVO, "250000")
        self.assertEqual(self._resolver(deductivo).status_code, 200)
        deductivo.refresh_from_db()
        self.assertEqual(deductivo.estado, ESTADO_SOLICITADO)

    def test_resolucion_requiere_numero(self):
        adicional = self._crear(TIPO_ADICIONAL, "1000")
        respuesta = self.client.post(reverse("calendario:adicional_resolver", args=[self.obra.pk, adicional.pk]), {
            "estado": "APROBADO", "fecha_aprobacion": date.today().isoformat(), "resolucion": "",
        })
        self.assertEqual(respuesta.status_code, 200)


class CalendarioFormTests(ModificacionesBase):
    def test_suma_de_avance_programado_no_supera_100(self):
        datos = {"periodo": self.obra.fecha_inicio.strftime("%Y-%m"), "monto_programado": "100000",
                 "avance_fisico_programado": "70"}
        form = CalendarioEjecucionForm(data=datos, obra=self.obra)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.obra = self.obra
        form.save()
        siguiente = (self.obra.fecha_inicio.replace(day=1) + timedelta(days=32)).strftime("%Y-%m")
        form = CalendarioEjecucionForm(data={**datos, "periodo": siguiente, "avance_fisico_programado": "40"}, obra=self.obra)
        self.assertFalse(form.is_valid())
        self.assertIn("avance_fisico_programado", form.errors)

    def test_montos_programados_no_superan_presupuesto_vigente(self):
        form = CalendarioEjecucionForm(data={"periodo": self.obra.fecha_inicio.strftime("%Y-%m"),
                                             "monto_programado": "250000", "avance_fisico_programado": "10"},
                                       obra=self.obra)
        self.assertFalse(form.is_valid())
        self.assertIn("monto_programado", form.errors)


class RecalculoFinancieroTests(TestCase):
    """RF-23: aprobar un adicional actualiza el avance financiero vigente, no los periodos anteriores."""

    def test_adicional_aprobado_recalcula_el_ultimo_avance(self):
        admin = Usuario.objects.create_user(username="adm_fin", password="Clave12345", rol=ROL_ADMIN)
        obra = Obra.objects.create(
            codigo="OB-FIN", nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=90,
            fecha_inicio=date(2026, 1, 1), fecha_fin_programada=date(2026, 4, 1), presupuesto_asignado=Decimal("1000"),
        )
        base = dict(obra=obra, avance_fisico_programado_acum=10, avance_fisico_ejecutado_acum=10, avance_financiero_programado_acum=10)
        previo = AvanceObra.objects.create(periodo=date(2026, 1, 1), avance_financiero_ejecutado_acum=25, monto_devengado_acum=250, **base)
        ultimo = AvanceObra.objects.create(periodo=date(2026, 2, 1), avance_financiero_ejecutado_acum=50, monto_devengado_acum=500, **base)
        adicional = AdicionalDeductivo.objects.create(
            obra=obra, tipo=TIPO_ADICIONAL, numero=1, monto=Decimal("250"), sustento="S", fecha_solicitud=date(2026, 2, 5),
        )
        self.client.force_login(admin)
        url = reverse("calendario:adicional_resolver", args=[obra.pk, adicional.pk])
        respuesta = self.client.post(url, {"estado": ESTADO_APROBADO, "fecha_aprobacion": "2026-02-10", "resolucion": "RA-1"})
        self.assertEqual(respuesta.status_code, 302)
        ultimo.refresh_from_db()
        previo.refresh_from_db()
        self.assertEqual(ultimo.avance_financiero_ejecutado_acum, Decimal("40.00"))
        self.assertEqual(previo.avance_financiero_ejecutado_acum, Decimal("25.00"))
