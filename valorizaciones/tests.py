"""
Pruebas de valorizaciones e informes mensuales (RF-16 a RF-19): flujo de
revisión residente -> supervisor, validaciones de montos y generación del
informe con los datos del periodo.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from avances.models import AvanceObra
from core.constants import ROL_ADMIN, ROL_RESIDENTE, ROL_SUPERVISOR
from obras.models import Obra
from usuarios.models import Usuario

from .models import (
    ESTADO_APROBADA,
    ESTADO_OBSERVADA,
    ESTADO_REGISTRADA,
    TIPO_INFORME_RESIDENTE,
    TIPO_INFORME_SUPERVISOR,
    InformeMensual,
    Valorizacion,
)


def _mes_anterior():
    return (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)


class ValorizacionBase(TestCase):
    def setUp(self):
        self.residente = Usuario.objects.create_user(username="res_val", password="Clave12345", rol=ROL_RESIDENTE)
        self.supervisor = Usuario.objects.create_user(username="sup_val", password="Clave12345", rol=ROL_SUPERVISOR)
        inicio = date.today() - timedelta(days=90)
        self.obra = Obra.objects.create(
            codigo="OB-VAL-01", nombre="Obra valorizaciones", meta_fisica="1 km", plazo_ejecucion_dias=180,
            fecha_inicio=inicio, fecha_fin_programada=inicio + timedelta(days=180),
            presupuesto_asignado=Decimal("100000.00"), residente=self.residente, supervisor=self.supervisor,
        )

    def _registrar(self, monto="20000", numero=1):
        self.client.force_login(self.residente)
        return self.client.post(reverse("valorizaciones:crear", args=[self.obra.pk]), {
            "numero": numero, "periodo": _mes_anterior().strftime("%Y-%m"), "monto": monto,
            "fecha_presentacion": date.today().isoformat(),
        })


class FlujoRevisionTests(ValorizacionBase):
    def test_flujo_observar_subsanar_y_aprobar(self):
        self.assertEqual(self._registrar().status_code, 302)
        valorizacion = Valorizacion.objects.get()
        self.assertEqual(valorizacion.estado, ESTADO_REGISTRADA)

        self.client.force_login(self.supervisor)
        url_revisar = reverse("valorizaciones:revisar", args=[valorizacion.pk])
        self.client.post(url_revisar, {"estado": ESTADO_OBSERVADA, "observaciones_revision": "Falta sustento"})
        valorizacion.refresh_from_db()
        self.assertEqual(valorizacion.estado, ESTADO_OBSERVADA)
        self.assertEqual(valorizacion.revisado_por, self.supervisor)

        # El residente corrige y la valorización vuelve a revisión
        self.client.force_login(self.residente)
        self.client.post(reverse("valorizaciones:subsanar", args=[valorizacion.pk]), {
            "numero": 1, "periodo": _mes_anterior().strftime("%Y-%m"), "monto": "18000",
            "fecha_presentacion": date.today().isoformat(),
        })
        valorizacion.refresh_from_db()
        self.assertEqual(valorizacion.estado, ESTADO_REGISTRADA)
        self.assertEqual(valorizacion.monto, Decimal("18000.00"))

        self.client.force_login(self.supervisor)
        self.client.post(url_revisar, {"estado": ESTADO_APROBADA, "observaciones_revision": ""})
        valorizacion.refresh_from_db()
        self.assertEqual(valorizacion.estado, ESTADO_APROBADA)
        # Una valorización ya revisada no puede volver a revisarse
        self.assertEqual(self.client.get(url_revisar).status_code, 404)

    def test_observar_exige_observaciones(self):
        self._registrar()
        valorizacion = Valorizacion.objects.get()
        self.client.force_login(self.supervisor)
        respuesta = self.client.post(reverse("valorizaciones:revisar", args=[valorizacion.pk]),
                                     {"estado": ESTADO_OBSERVADA, "observaciones_revision": ""})
        self.assertEqual(respuesta.status_code, 200)
        valorizacion.refresh_from_db()
        self.assertEqual(valorizacion.estado, ESTADO_REGISTRADA)

    def test_la_validacion_corresponde_solo_al_supervisor(self):
        self._registrar()
        valorizacion = Valorizacion.objects.get()
        admin = Usuario.objects.create_user(username="adm_val", password="Clave12345", rol=ROL_ADMIN)
        for usuario in (admin, self.residente):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("valorizaciones:revisar", args=[valorizacion.pk])).status_code, 403)

    def test_solo_se_subsanan_valorizaciones_observadas(self):
        self._registrar()
        valorizacion = Valorizacion.objects.get()
        self.assertEqual(self.client.get(reverse("valorizaciones:subsanar", args=[valorizacion.pk])).status_code, 404)


class ValidacionValorizacionTests(ValorizacionBase):
    def test_total_valorizado_no_supera_presupuesto_vigente(self):
        self.assertEqual(self._registrar(monto="120000").status_code, 200)
        self.assertFalse(Valorizacion.objects.exists())

    def test_numero_correlativo_no_se_repite(self):
        self._registrar()
        respuesta = self._registrar(numero=1)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Valorizacion.objects.count(), 1)


class InformeMensualTests(ValorizacionBase):
    def test_tipo_de_informe_segun_rol_y_datos_del_periodo(self):
        periodo = _mes_anterior()
        AvanceObra.objects.create(
            obra=self.obra, periodo=periodo, avance_fisico_programado_acum=Decimal("40"),
            avance_fisico_ejecutado_acum=Decimal("35"), avance_financiero_programado_acum=Decimal("40"),
            avance_financiero_ejecutado_acum=Decimal("30"), monto_devengado_acum=Decimal("30000"),
            observaciones="Se vació la losa del puente",
        )
        self._registrar()
        for usuario, tipo in ((self.residente, TIPO_INFORME_RESIDENTE), (self.supervisor, TIPO_INFORME_SUPERVISOR)):
            self.client.force_login(usuario)
            respuesta = self.client.post(reverse("valorizaciones:informe_crear", args=[self.obra.pk]), {
                "periodo": periodo.strftime("%Y-%m"), "resumen": "Avance conforme",
            })
            self.assertEqual(respuesta.status_code, 302)
            informe = InformeMensual.objects.get(tipo=tipo)
            self.assertEqual(informe.elaborado_por, usuario)

        datos = informe.datos_periodo()
        self.assertEqual(datos["avance"].avance_fisico_ejecutado_acum, Decimal("35"))
        self.assertEqual(datos["valorizaciones"].count(), 1)
        respuesta = self.client.get(reverse("valorizaciones:informe_detalle", args=[informe.pk]))
        self.assertContains(respuesta, "Se vació la losa del puente")

    def test_no_se_duplica_el_informe_del_periodo(self):
        self.client.force_login(self.residente)
        url = reverse("valorizaciones:informe_crear", args=[self.obra.pk])
        datos = {"periodo": _mes_anterior().strftime("%Y-%m"), "resumen": "Informe"}
        self.client.post(url, datos)
        self.assertEqual(self.client.post(url, datos).status_code, 200)
        self.assertEqual(InformeMensual.objects.count(), 1)
