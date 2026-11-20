"""
Pruebas de las utilidades compartidas: copias de respaldo (RNF-18),
protección de archivos subidos (RNF-17) y presentación de errores y
confirmaciones en la interfaz (RNF-10).
"""

import gzip
import json
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from avances.models import AvanceObra, EvidenciaAvance
from core.constants import ROL_ADMIN, ROL_ALTA_DIRECCION, ROL_APOYO, ROL_RESIDENTE, ROL_SUPERVISOR
from core.models import Bitacora
from core.validators import validar_documento, validar_pdf
from documentos.models import Documento, TipoDocumento
from obras.models import Obra
from usuarios.models import Usuario


class RespaldoBDTests(TestCase):
    def test_respaldo_json_genera_archivo_y_rota_copias(self):
        Usuario.objects.create_user(username="u_respaldo", password="Clave12345", rol=ROL_ADMIN)
        with tempfile.TemporaryDirectory() as carpeta, override_settings(BACKUP_DIR=carpeta, BACKUP_CONSERVAR=2):
            for _ in range(3):
                call_command("respaldar_bd", formato="json", stdout=StringIO())
            copias = sorted(Path(carpeta).glob("*.json.gz"))
            # Se conservan solo las 2 copias más recientes
            self.assertLessEqual(len(copias), 2)
            with gzip.open(copias[-1], "rt", encoding="utf-8") as f:
                datos = json.load(f)
            self.assertTrue(any(r["model"] == "usuarios.usuario" for r in datos))


class ArchivoProtegidoTests(TestCase):
    def test_anonimo_no_descarga_archivos_subidos(self):
        respuesta = self.client.get("/media/documentos/cualquiera.pdf")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("usuarios:login"), respuesta.url)

    def test_usuario_autenticado_no_puede_salir_de_media(self):
        usuario = Usuario.objects.create_user(username="u_media", password="Clave12345", rol=ROL_RESIDENTE)
        self.client.force_login(usuario)
        respuesta = self.client.get("/media/../manage.py")
        self.assertIn(respuesta.status_code, (400, 404))


_MEDIA_PRUEBAS = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_MEDIA_PRUEBAS)
class ArchivoPorObraTests(TestCase):
    """RF-04: el residente y el supervisor solo descargan los archivos de sus obras."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_PRUEBAS, ignore_errors=True)

    def setUp(self):
        self.residente = Usuario.objects.create_user(username="res_a", password="Clave12345", rol=ROL_RESIDENTE)
        self.ajeno = Usuario.objects.create_user(username="res_b", password="Clave12345", rol=ROL_RESIDENTE)
        self.supervisor = Usuario.objects.create_user(username="sup_a", password="Clave12345", rol=ROL_SUPERVISOR)
        self.sup_ajeno = Usuario.objects.create_user(username="sup_b", password="Clave12345", rol=ROL_SUPERVISOR)
        self.obra = Obra.objects.create(
            codigo="OB-ARCH", nombre="Obra", meta_fisica="1 km", plazo_ejecucion_dias=100,
            fecha_inicio=date(2026, 1, 1), fecha_fin_programada=date(2026, 4, 11),
            presupuesto_asignado=Decimal("1000"), residente=self.residente, supervisor=self.supervisor,
        )
        tipo = TipoDocumento.objects.create(nombre="Contrato")
        documento = Documento.objects.create(
            obra=self.obra, tipo_documento=tipo, nombre="Contrato", archivo=ContentFile(b"%PDF", name="contrato.pdf"),
        )
        self.url = documento.archivo.url
        avance = AvanceObra.objects.create(
            obra=self.obra, periodo=date(2026, 1, 1), avance_fisico_programado_acum=10, avance_fisico_ejecutado_acum=10,
            avance_financiero_programado_acum=10, avance_financiero_ejecutado_acum=10,
        )
        foto = EvidenciaAvance(avance=avance)
        contenido = BytesIO()
        Image.new("RGB", (10, 10)).save(contenido, "JPEG")
        foto.imagen.save("foto.jpg", ContentFile(contenido.getvalue()), save=True)
        self.url_foto = foto.imagen.url

    def _estado(self, usuario, url=None):
        self.client.force_login(usuario)
        return self.client.get(url or self.url).status_code

    def test_responsables_de_la_obra_descargan_sus_archivos(self):
        self.assertEqual(self._estado(self.residente), 200)
        self.assertEqual(self._estado(self.supervisor), 200)
        self.assertEqual(self._estado(self.residente, self.url_foto), 200)

    def test_responsables_de_otra_obra_no_descargan_archivos_ajenos(self):
        self.assertEqual(self._estado(self.ajeno), 404)
        self.assertEqual(self._estado(self.sup_ajeno), 404)
        self.assertEqual(self._estado(self.ajeno, self.url_foto), 404)

    def test_roles_con_vista_general_descargan_cualquier_archivo(self):
        for rol in (ROL_ADMIN, ROL_APOYO, ROL_ALTA_DIRECCION):
            usuario = Usuario.objects.create_user(username=f"u_{rol}", password="Clave12345", rol=rol)
            self.assertEqual(self._estado(usuario), 200)

    def test_archivo_sin_registro_no_se_entrega_al_residente(self):
        self.assertEqual(self._estado(self.residente, "/media/otros/huerfano.pdf"), 404)


class BitacoraTests(TestCase):
    """RNF-16: la bitácora registra lo que se guardó, no los formularios rechazados."""

    def setUp(self):
        self.admin = Usuario.objects.create_user(username="u_bit", password="Clave12345", rol=ROL_ADMIN)
        self.client.force_login(self.admin)

    def test_formulario_rechazado_no_se_registra(self):
        self.client.post(reverse("obras:crear"), {"codigo": ""})
        self.assertFalse(Bitacora.objects.exists())

    def test_operacion_guardada_se_registra(self):
        otro = Usuario.objects.create_user(username="u_bit2", password="Clave12345", rol=ROL_RESIDENTE)
        self.client.post(reverse("usuarios:toggle_activo", args=[otro.pk]))
        registro = Bitacora.objects.get()
        self.assertEqual((registro.usuario, registro.detalle), (self.admin, "toggle_activo"))


class ValidacionArchivosTests(TestCase):
    """RNF-17: tipo, contenido y tamaño de los archivos subidos."""

    def test_rechaza_extension_no_permitida(self):
        with self.assertRaises(ValidationError):
            validar_documento(SimpleUploadedFile("virus.exe", b"MZ"))

    def test_rechaza_pdf_falso(self):
        with self.assertRaises(ValidationError):
            validar_pdf(SimpleUploadedFile("expediente.pdf", b"esto no es un pdf"))

    def test_acepta_pdf_valido_y_documento_office(self):
        validar_pdf(SimpleUploadedFile("expediente.pdf", b"%PDF-1.4 contenido"))
        validar_documento(SimpleUploadedFile("planilla.xlsx", b"PK"))

    @override_settings(SUBIDA_MAX_MB=1)
    def test_rechaza_archivo_demasiado_grande(self):
        with self.assertRaises(ValidationError):
            validar_documento(SimpleUploadedFile("grande.pdf", b"%PDF-" + b"0" * 1024 * 1024))


class PaginasDeErrorTests(TestCase):
    """RNF-10, RNF-11: los errores se muestran con el diseño del sistema."""

    def test_403_y_404_con_el_diseno_del_sistema(self):
        residente = Usuario.objects.create_user(username="u_err", password="Clave12345", rol=ROL_RESIDENTE)
        self.client.force_login(residente)
        self.assertContains(self.client.get(reverse("usuarios:lista")), "Acceso no permitido", status_code=403)
        with override_settings(DEBUG=False):
            self.assertContains(self.client.get("/no-existe/"), "No se encontró", status_code=404)


class CompresionTests(TestCase):
    """RNF-08: las respuestas HTML y JSON viajan comprimidas."""

    def test_respuesta_comprimida_con_gzip(self):
        admin = Usuario.objects.create_user(username="u_gz", password="Clave12345", rol=ROL_ADMIN)
        self.client.force_login(admin)
        respuesta = self.client.get(reverse("reportes:dashboard"), headers={"accept-encoding": "gzip"})
        self.assertEqual(respuesta.headers.get("Content-Encoding"), "gzip")


class InterfazErroresTests(TestCase):
    def test_formulario_invalido_muestra_resumen_de_errores(self):
        admin = Usuario.objects.create_user(username="u_admin_err", password="Clave12345", rol=ROL_ADMIN)
        self.client.force_login(admin)
        respuesta = self.client.post(reverse("obras:crear"), {"codigo": ""})
        self.assertContains(respuesta, "No se guardó la información")
        self.assertContains(respuesta, "campos-con-error")
