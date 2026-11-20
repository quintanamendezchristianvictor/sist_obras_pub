"""
Pruebas unitarias del módulo de avances: verifican el cálculo automático de
la desviación y la clasificación semafórica del avance (RF-14), base de las
alertas del dashboard dinámico (RF-32), y los cálculos y validaciones del
registro de avance (RF-11 a RF-14, RNF-02).
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from calendario.models import ESTADO_APROBADO, TIPO_ADICIONAL, AdicionalDeductivo, CalendarioEjecucion
from core.constants import ROL_RESIDENTE, SEMAFORO_A_TIEMPO, SEMAFORO_ATRASADA, SEMAFORO_EN_RIESGO
from obras.models import ExpedienteTecnico, Obra, PartidaExpediente
from usuarios.models import Usuario

from .forms import AvanceObraForm
from .models import AvanceObra


class AvanceSemaforoTests(TestCase):
    def setUp(self):
        self.obra = Obra.objects.create(
            codigo="OB-TEST-002",
            nombre="Obra de prueba 2",
            meta_fisica="1.0 km",
            plazo_ejecucion_dias=100,
            fecha_inicio=date.today() - timedelta(days=30),
            fecha_fin_programada=date.today() + timedelta(days=70),
            presupuesto_asignado=Decimal("50000.00"),
        )

    def _crear_avance(self, programado, ejecutado):
        return AvanceObra.objects.create(
            obra=self.obra,
            periodo=date.today().replace(day=1),
            avance_fisico_programado_acum=Decimal(programado),
            avance_fisico_ejecutado_acum=Decimal(ejecutado),
            avance_financiero_programado_acum=Decimal(programado),
            avance_financiero_ejecutado_acum=Decimal(ejecutado),
        )

    def test_obra_a_tiempo(self):
        avance = self._crear_avance(50, 48)
        self.assertEqual(avance.estado_semaforo, SEMAFORO_A_TIEMPO)

    def test_obra_en_riesgo(self):
        avance = self._crear_avance(50, 38)  # desviación = 12 (>= 10, < 20)
        self.assertEqual(avance.estado_semaforo, SEMAFORO_EN_RIESGO)

    def test_obra_atrasada(self):
        avance = self._crear_avance(80, 50)  # desviación = 30 (>= 20)
        self.assertEqual(avance.estado_semaforo, SEMAFORO_ATRASADA)

    def test_desviacion_fisica_calculada(self):
        avance = self._crear_avance(60, 45)
        self.assertEqual(avance.desviacion_fisica, 15.0)


def _mes(desplazamiento):
    """Primer día del mes actual desplazado `desplazamiento` meses."""
    hoy = date.today()
    total = hoy.year * 12 + hoy.month - 1 + desplazamiento
    return date(total // 12, total % 12 + 1, 1)


class AvanceFormCalculoTests(TestCase):
    """
    Verifica RF-12, RF-13, RF-14 y RF-20: el residente solo ingresa lo
    ejecutado y el sistema calcula los porcentajes programados (desde el
    calendario) y el avance financiero (desde el monto devengado).
    """

    def setUp(self):
        self.obra = Obra.objects.create(
            codigo="OB-FORM-01", nombre="Obra formulario", meta_fisica="1 km", plazo_ejecucion_dias=90,
            fecha_inicio=_mes(-2), fecha_fin_programada=_mes(-2) + timedelta(days=90),
            presupuesto_asignado=Decimal("100000.00"),
        )
        for i, (fisico, monto) in enumerate([(30, 20000), (40, 50000), (30, 30000)]):
            CalendarioEjecucion.objects.create(
                obra=self.obra, periodo=_mes(-2 + i), monto_programado=Decimal(monto),
                avance_fisico_programado=Decimal(fisico),
            )

    def _form(self, **datos):
        base = {"periodo": _mes(-1).strftime("%Y-%m"), "avance_fisico_ejecutado_acum": "50",
                "monto_devengado_acum": "45000", "observaciones": ""}
        base.update(datos)
        return AvanceObraForm(data=base, obra=self.obra)

    def test_calcula_programado_desde_calendario_y_financiero_desde_devengado(self):
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)
        avance = form.save(commit=False)
        self.assertEqual(avance.avance_fisico_programado_acum, Decimal("70.00"))       # 30 + 40
        self.assertEqual(avance.avance_financiero_programado_acum, Decimal("70.00"))   # 70 000 / 100 000
        self.assertEqual(avance.avance_financiero_ejecutado_acum, Decimal("45.00"))    # 45 000 / 100 000
        self.assertEqual(avance.periodo, _mes(-1))

    def test_financiero_usa_presupuesto_vigente(self):
        AdicionalDeductivo.objects.create(
            obra=self.obra, tipo=TIPO_ADICIONAL, numero=1, monto=Decimal("25000"), sustento="x",
            estado=ESTADO_APROBADO, fecha_solicitud=date.today(),
        )
        form = self._form(monto_devengado_acum="50000")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.avance_financiero_ejecutado_acum, Decimal("40.00"))  # 50 000 / 125 000

    def test_rechaza_porcentaje_mayor_a_100(self):
        self.assertFalse(self._form(avance_fisico_ejecutado_acum="120").is_valid())

    def test_rechaza_devengado_mayor_al_presupuesto(self):
        self.assertFalse(self._form(monto_devengado_acum="150000").is_valid())

    def test_rechaza_periodo_futuro(self):
        self.assertFalse(self._form(periodo=_mes(1).strftime("%Y-%m")).is_valid())

    def test_ejecutado_no_puede_retroceder(self):
        form = self._form(periodo=_mes(-2).strftime("%Y-%m"), avance_fisico_ejecutado_acum="40",
                          monto_devengado_acum="30000")
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        form = self._form(avance_fisico_ejecutado_acum="35")
        self.assertFalse(form.is_valid())
        self.assertIn("avance_fisico_ejecutado_acum", form.errors)

    def test_sin_calendario_pide_programado_manual(self):
        self.obra.calendario.all().delete()
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn("avance_fisico_programado_acum", form.errors)
        form = self._form(avance_fisico_programado_acum="60", avance_financiero_programado_acum="55")
        self.assertTrue(form.is_valid(), form.errors)

    def test_fisico_desde_metrados_de_partidas(self):
        """RF-11: con partidas, el % físico = costo de lo ejecutado / costo total."""
        expediente = ExpedienteTecnico.objects.create(
            obra=self.obra, numero_expediente="ET-1", fecha_aprobacion=_mes(-3), monto_expediente=Decimal("100000"),
        )
        p1 = PartidaExpediente.objects.create(expediente=expediente, item="01", descripcion="Concreto",
                                              unidad="m3", metrado=Decimal("100"), precio_unitario=Decimal("600"))
        p2 = PartidaExpediente.objects.create(expediente=expediente, item="02", descripcion="Acabados",
                                              unidad="m2", metrado=Decimal("400"), precio_unitario=Decimal("100"))
        form = AvanceObraForm(data={
            "periodo": _mes(-1).strftime("%Y-%m"), "monto_devengado_acum": "40000",
            f"metrado_{p1.pk}": "50", f"metrado_{p2.pk}": "100",
        }, obra=self.obra)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.obra = self.obra
        avance = form.save()
        # (50 x 600 + 100 x 100) / (100 x 600 + 400 x 100) = 40 000 / 100 000
        self.assertEqual(avance.avance_fisico_ejecutado_acum, Decimal("40.00"))
        self.assertEqual(avance.metrados.count(), 2)

    def test_metrado_no_supera_lo_programado(self):
        expediente = ExpedienteTecnico.objects.create(
            obra=self.obra, numero_expediente="ET-2", fecha_aprobacion=_mes(-3), monto_expediente=Decimal("100000"),
        )
        partida = PartidaExpediente.objects.create(expediente=expediente, item="01", descripcion="Concreto",
                                                   unidad="m3", metrado=Decimal("10"), precio_unitario=Decimal("10"))
        form = AvanceObraForm(data={"periodo": _mes(-1).strftime("%Y-%m"), "monto_devengado_acum": "100",
                                    f"metrado_{partida.pk}": "11"}, obra=self.obra)
        self.assertFalse(form.is_valid())


class AvanceVistasTests(TestCase):
    def setUp(self):
        self.residente = Usuario.objects.create_user(username="res_av", password="Clave12345", rol=ROL_RESIDENTE)
        self.obra = Obra.objects.create(
            codigo="OB-VIS-01", nombre="Obra vistas", meta_fisica="1 km", plazo_ejecucion_dias=90,
            fecha_inicio=_mes(-2), fecha_fin_programada=_mes(-2) + timedelta(days=90),
            presupuesto_asignado=Decimal("100000.00"), residente=self.residente,
        )
        self.client.force_login(self.residente)

    def _registrar(self, periodo, fisico, monto):
        return self.client.post(reverse("avances:crear", args=[self.obra.pk]), {
            "periodo": periodo.strftime("%Y-%m"), "avance_fisico_ejecutado_acum": fisico,
            "monto_devengado_acum": monto, "avance_fisico_programado_acum": "50",
            "avance_financiero_programado_acum": "50",
        })

    def test_registro_y_correccion_solo_del_ultimo_avance(self):
        self.assertEqual(self._registrar(_mes(-2), "20", "10000").status_code, 302)
        self.assertEqual(self._registrar(_mes(-1), "40", "30000").status_code, 302)
        primero, ultimo = self.obra.avances.order_by("periodo")
        self.assertEqual(self.client.get(reverse("avances:editar", args=[ultimo.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("avances:editar", args=[primero.pk])).status_code, 404)
