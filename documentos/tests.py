"""Pruebas de la búsqueda del acervo documentario (RF-25, RF-26) con visibilidad por rol (RF-04)."""

import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.constants import ROL_ALTA_DIRECCION, ROL_RESIDENTE
from obras.models import Obra
from usuarios.models import Usuario

from .models import Documento, TipoDocumento

_MEDIA_PRUEBAS = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_MEDIA_PRUEBAS)
class BusquedaDocumentosTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_PRUEBAS, ignore_errors=True)

    def setUp(self):
        self.residente = Usuario.objects.create_user(username="res_doc", password="Clave12345", rol=ROL_RESIDENTE)
        datos = dict(meta_fisica="1 km", plazo_ejecucion_dias=100, fecha_inicio=date.today() - timedelta(days=30),
                     fecha_fin_programada=date.today() + timedelta(days=70), presupuesto_asignado=Decimal("1000"))
        self.propia = Obra.objects.create(codigo="OB-D1", nombre="Propia", residente=self.residente, **datos)
        self.ajena = Obra.objects.create(codigo="OB-D2", nombre="Ajena", **datos)
        self.acta = TipoDocumento.objects.create(nombre="Acta")
        self.contrato = TipoDocumento.objects.create(nombre="Contrato")
        for obra, tipo, nombre, periodo in [
            (self.propia, self.acta, "Acta de entrega de terreno", date(2026, 3, 1)),
            (self.propia, self.contrato, "Contrato de obra", date(2026, 4, 1)),
            (self.ajena, self.acta, "Acta de la obra ajena", date(2026, 3, 1)),
        ]:
            Documento.objects.create(obra=obra, tipo_documento=tipo, nombre=nombre, periodo=periodo,
                                     archivo=ContentFile(b"%PDF", name="doc.pdf"))

    def _buscar(self, usuario, **filtros):
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse("documentos:buscar"), filtros)
        self.assertEqual(respuesta.status_code, 200)
        return [d.nombre for d in respuesta.context["documentos"]]

    def test_residente_solo_encuentra_documentos_de_sus_obras(self):
        self.assertEqual(sorted(self._buscar(self.residente)), ["Acta de entrega de terreno", "Contrato de obra"])

    def test_alta_direccion_busca_en_todas_las_obras(self):
        direccion = Usuario.objects.create_user(username="dir_doc", password="Clave12345", rol=ROL_ALTA_DIRECCION)
        self.assertEqual(len(self._buscar(direccion)), 3)
        self.assertEqual(self._buscar(direccion, obra=self.ajena.pk), ["Acta de la obra ajena"])

    def test_filtros_por_texto_tipo_y_periodo(self):
        self.assertEqual(self._buscar(self.residente, q="terreno"), ["Acta de entrega de terreno"])
        self.assertEqual(self._buscar(self.residente, tipo=self.contrato.pk), ["Contrato de obra"])
        self.assertEqual(self._buscar(self.residente, periodo="2026-03"), ["Acta de entrega de terreno"])
