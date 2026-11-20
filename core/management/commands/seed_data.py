"""
Comando de gestión para poblar la base de datos MySQL con datos de prueba
realistas: aproximadamente 100 registros por tabla de dominio, tal como fue
solicitado para la sustentación y pruebas del sistema.

Uso:
    python manage.py seed_data
    python manage.py seed_data --total 100 --flush

Las tablas de catálogo (tipos de documento) y de configuración (singleton)
se excluyen deliberadamente del conteo de 100 registros por no ser
realistas en ese volumen; se documenta esta excepción en el README.
"""

import io
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker
from PIL import Image, ImageDraw
from xhtml2pdf import pisa

from avances.models import AvanceObra, EvidenciaAvance, MetradoEjecutado
from calendario.models import (
    ESTADO_ADICIONAL_DEDUCTIVO_CHOICES,
    ESTADO_AMPLIACION_CHOICES,
    ESTADO_APROBADA,
    TIPO_ADICIONAL_DEDUCTIVO_CHOICES,
    AdicionalDeductivo,
    AmpliacionPlazo,
    CalendarioEjecucion,
)
from core.constants import (
    ESTADO_CON_RETRASO,
    ESTADO_CONCLUIDA,
    ESTADO_PARALIZADA,
    ESTADOS_OBRA_CHOICES,
    MODALIDAD_CONTRATA,
    MODALIDAD_EJECUCION_CHOICES,
    NATURALEZA_OBRA_CHOICES,
    ROL_ADMIN,
    ROL_ALTA_DIRECCION,
    ROL_APOYO,
    ROL_RESIDENTE,
    ROL_SUPERVISOR,
    UNIDADES_ORGANICAS_SUGERIDAS,
)
from core.models import Bitacora, Configuracion
from documentos.models import Documento, TipoDocumento
from obras.models import ExpedienteTecnico, FichaInfobras, Obra, ParalizacionObra, PartidaExpediente
from usuarios.models import Usuario
from valorizaciones.models import ESTADO_REGISTRADA, ESTADO_VALORIZACION_CHOICES, TIPO_INFORME_CHOICES, InformeMensual, Valorizacion

fake = Faker("es_ES")

PASSWORD_DEMO = "Clave12345"

NOMBRES_OBRA = [
    "Mejoramiento de la vía vecinal {lugar}",
    "Construcción del sistema de agua potable y saneamiento en {lugar}",
    "Rehabilitación del local comunal de {lugar}",
    "Ampliación del servicio de electrificación rural en {lugar}",
    "Construcción de la losa deportiva multiusos de {lugar}",
    "Mejoramiento del canal de riego {lugar}",
    "Construcción del puente carrozable {lugar}",
    "Mejoramiento de la infraestructura educativa de la I.E. {lugar}",
    "Construcción del parque recreativo de {lugar}",
    "Mejoramiento del sistema de alcantarillado de {lugar}",
]

LUGARES = [
    "Santa Rosa", "Pampay", "Huallhua", "Chaca", "Ccochapampa", "Qasanqay",
    "San Miguel", "Vista Alegre", "Chontaca", "Ninabamba", "Rosaspata",
    "Patibamba", "Totorilla", "Accomarca", "Villa Florida",
]

TIPOS_DOCUMENTO = [
    "Expediente Técnico", "Acta de Entrega de Terreno", "Resolución de Aprobación",
    "Contrato de Ejecución de Obra", "Informe de Supervisión", "Panel Fotográfico",
    "Acta de Recepción de Obra", "Otro",
]

# Nombres y apellidos peruanos (no se usa Faker para esto: el locale "es_ES"
# de Faker genera onomástica española/ibérica, no representativa de la
# población peruana real que el sistema modela). Se usan listas curadas de
# nombres de pila y apellidos comunes en el Perú (incluye apellidos de
# origen quechua muy frecuentes en Ayacucho, además de los de origen
# hispano más comunes a nivel nacional).
NOMBRES_MASCULINOS = [
    "Carlos", "Luis", "José", "Juan", "Miguel", "Jorge", "Víctor", "Pedro",
    "Raúl", "Edwin", "Walter", "Rubén", "Wilson", "Elmer", "Edgar", "Alberto",
    "Marco", "Manuel", "Francisco", "Ricardo", "Fernando", "Alex", "Abel",
    "Percy", "Ricardo", "Henry", "Nilton", "Yuri", "Rolando", "Teodoro",
    "Hugo", "Oscar", "Javier", "Alfredo", "Wilfredo", "Darío", "Julio",
    "Américo", "Ever", "Erick", "Saúl", "Moisés", "David", "Samuel",
    "Mario", "Ronald", "Segundo", "Fidel", "Gregorio", "Ciro",
]

NOMBRES_FEMENINOS = [
    "María", "Rosa", "Juana", "Carmen", "Flor", "Elena", "Gladys", "Yolanda",
    "Luz", "Mariela", "Katherine", "Vilma", "Nelly", "Soledad", "Yaneth",
    "Edith", "Marisol", "Giovanna", "Milagros", "Paola", "Karina", "Lucía",
    "Fiorella", "Esperanza", "Victoria", "Teodora", "Zenobia", "Cristina",
    "Doris", "Rocío", "Yesenia", "Haydee", "Noemí", "Olinda", "Yolvi",
    "Reyna", "Elizabeth", "Consuelo", "Marleni", "Dina", "Ruth", "Sonia",
    "Diana", "Brigida", "Juliana", "Celia", "Antonia", "Herminia",
]

APELLIDOS_PERUANOS = [
    "Quispe", "Mamani", "Huamán", "Rojas", "Flores", "Gonzales", "Vargas",
    "Cárdenas", "Huamani", "Taipe", "Cusihuaman", "Palomino", "Ccopa",
    "Chávez", "Rivera", "Carrasco", "Salazar", "Mendoza", "Cárdenas",
    "Ramos", "Fernández", "Torres", "Gutiérrez", "Paredes", "Huaraca",
    "Ccoyllo", "Ñahui", "Curasma", "Berrocal", "Crisóstomo", "Quintana",
    "Espinoza", "Cahuana", "Ayala", "Vega", "Soto", "Ochoa", "Romero",
    "Loayza", "Prado", "Meza", "Cisneros", "Zamora", "Inga", "Matos",
    "Pariona", "Allcca", "Tineo", "Bautista", "Yupanqui", "Cordova",
    "Huayta", "Yauri", "Anccasi", "Guillén", "Medina", "Rojas", "Castillo",
    "Ortega", "Villanueva", "Espinal", "Morales", "Bendezú", "Navarro",
]


def nombre_y_apellidos_peruanos():
    """Genera (sexo, nombre_de_pila, 'Apellido Apellido') con nombres peruanos."""
    genero = random.choice(["M", "F"])
    nombre = random.choice(NOMBRES_MASCULINOS if genero == "M" else NOMBRES_FEMENINOS)
    apellido_paterno = random.choice(APELLIDOS_PERUANOS)
    apellido_materno = random.choice(APELLIDOS_PERUANOS)
    while apellido_materno == apellido_paterno:
        apellido_materno = random.choice(APELLIDOS_PERUANOS)
    return genero, nombre, f"{apellido_paterno} {apellido_materno}"


def imagen_evidencia(texto):
    """Genera una imagen JPEG simple (placeholder) a modo de evidencia fotográfica."""
    color_fondo = random.choice([(96, 125, 139), (31, 78, 120), (56, 142, 60), (121, 85, 72)])
    img = Image.new("RGB", (640, 420), color=color_fondo)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 629, 409], outline=(255, 255, 255), width=3)
    draw.text((30, 190), texto, fill=(255, 255, 255))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75)
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"evidencia_{random.randint(1, 999999)}.jpg")


def pdf_simulado(titulo, parrafo):
    """Genera un PDF real y válido (vía xhtml2pdf) a modo de documento de prueba."""
    html = f"""
    <html><body style="font-family: Helvetica; font-size: 11pt;">
    <h2 style="color:#1f4e78;">{titulo}</h2>
    <p>{parrafo}</p>
    <p style="color:#888; font-size:9pt;">Documento generado automáticamente para fines de prueba del sistema.</p>
    </body></html>
    """
    buffer = io.BytesIO()
    pisa.CreatePDF(src=html, dest=buffer, encoding="utf-8")
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f"documento_{random.randint(1, 999999)}.pdf")


def _sumar_meses(fecha, meses):
    """Primer día del mes que está `meses` después de `fecha`."""
    total = fecha.year * 12 + fecha.month - 1 + meses
    return date(total // 12, total % 12 + 1, 1)


def fecha_aleatoria(dias_atras_min, dias_atras_max):
    dias = random.randint(dias_atras_min, dias_atras_max)
    return date.today() - timedelta(days=dias)


class Command(BaseCommand):
    help = "Genera datos de prueba (aprox. 100 registros por tabla) en la base de datos MySQL."

    def add_arguments(self, parser):
        parser.add_argument("--total", type=int, default=100, help="Cantidad de obras/usuarios a generar (por defecto 100).")
        parser.add_argument("--flush", action="store_true", help="Elimina los datos de dominio existentes antes de generar los nuevos.")

    def handle(self, *args, **options):
        total = options["total"]
        hacer_flush = options["flush"]

        if Obra.objects.exists() and not hacer_flush:
            self.stderr.write(self.style.ERROR(
                "Ya existen obras registradas. Ejecute el comando con --flush para "
                "reemplazar los datos de prueba, o trabaje sobre los datos actuales."
            ))
            return

        with transaction.atomic():
            if hacer_flush:
                self._limpiar()

            self.stdout.write("Creando catálogos y configuración inicial...")
            self._crear_configuracion()
            tipos_documento = self._crear_tipos_documento()

            self.stdout.write(f"Creando {total} usuarios...")
            usuarios = self._crear_usuarios(total)

            self.stdout.write(f"Creando {total} obras...")
            obras = self._crear_obras(total, usuarios)

            self.stdout.write("Creando expedientes técnicos...")
            self._crear_expedientes(obras)

            self.stdout.write("Registrando datos para INFOBRAS y paralizaciones...")
            self._crear_fichas_infobras(obras)

            self.stdout.write("Generando calendario de ejecución...")
            self._crear_calendario(obras)

            self.stdout.write("Registrando ampliaciones de plazo...")
            self._crear_ampliaciones(obras, usuarios)

            self.stdout.write("Registrando adicionales y deductivos...")
            self._crear_adicionales(obras, usuarios)

            self.stdout.write("Registrando avances físicos y financieros + evidencias...")
            self._crear_avances(obras, usuarios)

            self.stdout.write("Registrando valorizaciones...")
            self._crear_valorizaciones(obras, usuarios)

            self.stdout.write("Generando informes mensuales...")
            self._crear_informes(obras, usuarios)

            self.stdout.write("Cargando documentos al acervo documentario...")
            self._crear_documentos(obras, usuarios, tipos_documento)

            self.stdout.write("Generando bitácora histórica de ejemplo...")
            self._crear_bitacora(usuarios, total)

        self.stdout.write(self.style.SUCCESS(
            f"\nListo. Se generaron {total} registros por tabla de dominio.\n"
            f"Usuarios de acceso rápido (contraseña para todos: '{PASSWORD_DEMO}'):\n"
            f"  admin001         -> Administrador del sistema\n"
            f"  apoyo001         -> Personal administrativo de apoyo\n"
            f"  residente001     -> Residente de obra\n"
            f"  supervisor001    -> Supervisor / Inspector de obra\n"
            f"  direccion001     -> Alta dirección\n"
        ))

    # ------------------------------------------------------------------
    def _limpiar(self):
        Bitacora.objects.all().delete()
        Documento.objects.all().delete()
        AdicionalDeductivo.objects.all().delete()
        AmpliacionPlazo.objects.all().delete()
        CalendarioEjecucion.objects.all().delete()
        InformeMensual.objects.all().delete()
        Valorizacion.objects.all().delete()
        EvidenciaAvance.objects.all().delete()
        AvanceObra.objects.all().delete()
        ExpedienteTecnico.objects.all().delete()
        Obra.objects.all().delete()
        # Se eliminan todos los usuarios generados por este mismo comando
        # (incluido el superusuario "admin001") para permitir regenerar un
        # conjunto de datos de prueba limpio con --flush. Si ha creado
        # manualmente otras cuentas de administrador fuera de este comando,
        # ejecute --flush con precaución.
        Usuario.objects.all().delete()

    def _crear_configuracion(self):
        Configuracion.actual()

    def _crear_tipos_documento(self):
        tipos = []
        for nombre in TIPOS_DOCUMENTO:
            tipo, _ = TipoDocumento.objects.get_or_create(nombre=nombre)
            tipos.append(tipo)
        return tipos

    # ------------------------------------------------------------------
    def _crear_usuarios(self, total):
        """
        Distribuye el total de usuarios entre los 5 roles del sistema,
        garantizando al menos un usuario de acceso rápido y predecible por rol.
        """
        distribucion = {
            ROL_ADMIN: max(2, round(total * 0.03)),
            ROL_APOYO: round(total * 0.12),
            ROL_RESIDENTE: round(total * 0.35),
            ROL_SUPERVISOR: round(total * 0.35),
            ROL_ALTA_DIRECCION: 0,  # se completa abajo con el resto
        }
        asignados = sum(distribucion.values())
        distribucion[ROL_ALTA_DIRECCION] = max(2, total - asignados)

        prefijos = {
            ROL_ADMIN: "admin",
            ROL_APOYO: "apoyo",
            ROL_RESIDENTE: "residente",
            ROL_SUPERVISOR: "supervisor",
            ROL_ALTA_DIRECCION: "direccion",
        }
        cargos = {
            ROL_ADMIN: "Administrador de sistemas",
            ROL_APOYO: "Asistente administrativo",
            ROL_RESIDENTE: "Residente de obra",
            ROL_SUPERVISOR: "Supervisor de obra",
            ROL_ALTA_DIRECCION: "Gerente municipal",
        }

        usuarios_por_rol = {rol: [] for rol in prefijos}
        dni_actual = 40000001
        clave_cifrada = make_password(PASSWORD_DEMO)  # cifrar una sola vez: cada cifrado tarda cerca de 1 s

        for rol, cantidad in distribucion.items():
            for i in range(1, cantidad + 1):
                username = f"{prefijos[rol]}{i:03d}"
                sexo, nombres, apellidos = nombre_y_apellidos_peruanos()
                usuario = Usuario(
                    username=username,
                    first_name=nombres,
                    last_name=apellidos,
                    email=f"{username}@santarosa.gob.pe",
                    sexo=sexo,
                    dni=str(dni_actual),
                    telefono=f"9{random.randint(10000000, 99999999)}",
                    cargo=cargos[rol],
                    unidad_organica="Subgerencia de Infraestructura",
                    rol=rol,
                    is_active=True,
                    is_staff=(rol == ROL_ADMIN),
                    is_superuser=(rol == ROL_ADMIN and i == 1),
                )
                usuario.password = clave_cifrada
                usuario.save()
                usuarios_por_rol[rol].append(usuario)
                dni_actual += 1

        return usuarios_por_rol

    # ------------------------------------------------------------------
    def _crear_obras(self, total, usuarios):
        residentes = usuarios[ROL_RESIDENTE]
        supervisores = usuarios[ROL_SUPERVISOR]
        admin = usuarios[ROL_ADMIN][0]

        estados = [e[0] for e in ESTADOS_OBRA_CHOICES]
        pesos_estado = [0.55, 0.10, 0.20, 0.15]  # en_ejecucion, paralizada, concluida, con_retraso
        modalidades = [m[0] for m in MODALIDAD_EJECUCION_CHOICES]

        obras = []
        for i in range(1, total + 1):
            plantilla = random.choice(NOMBRES_OBRA)
            lugar = random.choice(LUGARES)
            nombre = plantilla.format(lugar=lugar)

            estado = random.choices(estados, weights=pesos_estado, k=1)[0]
            plazo_dias = random.choice([90, 120, 150, 180, 210, 270, 365])
            if estado == ESTADO_CONCLUIDA:
                # Una obra concluida ya cumplió su plazo: su fecha de fin queda en el pasado
                fecha_inicio = fecha_aleatoria(plazo_dias + 15, plazo_dias + 540)
            else:
                fecha_inicio = fecha_aleatoria(60, 540)
            fecha_fin = fecha_inicio + timedelta(days=plazo_dias)
            presupuesto = Decimal(random.randint(80_000, 3_500_000))

            modalidad = random.choice(modalidades)
            por_contrata = modalidad == MODALIDAD_CONTRATA
            obra = Obra.objects.create(
                codigo=f"OB-{2024 + (i % 3)}-{i:04d}",
                nombre=nombre,
                descripcion=fake.text(max_nb_chars=180),
                direccion=f"Sector {lugar}",
                distrito="Santa Rosa",
                provincia="La Mar",
                departamento="Ayacucho",
                modalidad_ejecucion=modalidad,
                contratista=f"Constructora {random.choice(APELLIDOS_PERUANOS)} {random.choice(['S.A.C.', 'E.I.R.L.', 'S.R.L.'])}" if por_contrata else "",
                contratista_ruc=f"20{random.randint(100000000, 999999999)}" if por_contrata else "",
                meta_fisica=f"{random.randint(1, 10)}.{random.randint(0,9)} {random.choice(['km', 'ml', 'm2', 'unidad'])}",
                unidad_medida=random.choice(["km", "ml", "m2", "unidad", "glb"]),
                plazo_ejecucion_dias=plazo_dias,
                fecha_inicio=fecha_inicio,
                fecha_fin_programada=fecha_fin,
                presupuesto_asignado=presupuesto,
                estado=estado,
                unidad_organica=random.choices(UNIDADES_ORGANICAS_SUGERIDAS, weights=[0.55, 0.2, 0.15, 0.1], k=1)[0],
                residente=random.choice(residentes),
                supervisor=random.choice(supervisores),
                creado_por=admin,
            )
            obras.append(obra)
        return obras

    def _crear_expedientes(self, obras):
        for obra in obras:
            ExpedienteTecnico.objects.create(
                obra=obra,
                numero_expediente=f"ET-{obra.fecha_inicio.year}-{obra.pk:04d}",
                entidad_formuladora="Subgerencia de Infraestructura - MDSR",
                fecha_aprobacion=obra.fecha_inicio - timedelta(days=random.randint(10, 60)),
                monto_expediente=obra.presupuesto_asignado,
                observaciones=fake.sentence(nb_words=12),
            )
            if obra.pk % 5 == 0:
                self._crear_partidas(obra)

    def _crear_fichas_infobras(self, obras):
        for obra in obras:
            por_contrata = obra.modalidad_ejecucion == MODALIDAD_CONTRATA
            concluida = obra.estado == ESTADO_CONCLUIDA
            recepcion = obra.fecha_fin_programada + timedelta(days=random.randint(5, 25)) if concluida else None
            FichaInfobras.objects.create(
                obra=obra,
                naturaleza=random.choice(NATURALEZA_OBRA_CHOICES)[0],
                latitud=Decimal(f"-{random.randint(12, 13)}.{random.randint(100000, 999999)}"),
                longitud=Decimal(f"-{random.randint(73, 74)}.{random.randint(100000, 999999)}"),
                fecha_entrega_terreno=obra.fecha_inicio - timedelta(days=random.randint(1, 10)),
                contrato_numero=f"CONT-{obra.fecha_inicio.year}-{obra.pk:04d}" if por_contrata else "",
                contrato_fecha=obra.fecha_inicio - timedelta(days=random.randint(10, 30)) if por_contrata else None,
                contrato_monto=obra.presupuesto_asignado if por_contrata else None,
                adelanto_directo=(obra.presupuesto_asignado * Decimal("0.10")).quantize(Decimal("0.01")) if por_contrata else None,
                recepcion_fecha=recepcion,
                recepcion_acta=f"ACTA-{obra.pk:04d}" if concluida else "",
                liquidacion_fecha=recepcion + timedelta(days=60) if concluida else None,
                liquidacion_monto=obra.presupuesto_asignado if concluida else None,
                liquidacion_resolucion=f"RGM-{obra.pk:04d}-MDSR" if concluida else "",
            )
            if obra.estado == ESTADO_PARALIZADA:
                ParalizacionObra.objects.create(
                    obra=obra, fecha_inicio=obra.fecha_inicio + timedelta(days=30),
                    motivo=random.choice(["Falta de materiales", "Lluvias intensas", "Conflicto social", "Falta de presupuesto"]),
                )

    def _crear_partidas(self, obra):
        """Cuatro partidas cuyo costo total coincide con el presupuesto de la obra (RF-11)."""
        plantilla = [
            ("01.01", "Trabajos preliminares", "glb", Decimal("0.05")),
            ("02.01", "Movimiento de tierras", "m3", Decimal("0.25")),
            ("03.01", "Obras de concreto", "m3", Decimal("0.50")),
            ("04.01", "Acabados y varios", "m2", Decimal("0.20")),
        ]
        expediente = obra.expediente_tecnico
        for item, descripcion, unidad, peso in plantilla:
            metrado = Decimal(1) if unidad == "glb" else Decimal(random.randint(200, 3000))
            precio = (obra.presupuesto_asignado * peso / metrado).quantize(Decimal("0.01"))
            PartidaExpediente.objects.create(
                expediente=expediente, item=item, descripcion=descripcion,
                unidad=unidad, metrado=metrado, precio_unitario=precio,
            )

    def _crear_avances(self, obras, usuarios):
        """
        Avances mensuales desde el inicio de la obra hasta el mes actual (o su
        culminación), coherentes con las reglas del sistema (RF-11 a RF-14):
        el programado sale del calendario, el financiero del monto devengado
        y el ejecutado nunca retrocede.
        """
        hoy = date.today().replace(day=1)
        for obra in obras:
            vigente = obra.presupuesto_vigente
            calendario = list(obra.calendario.order_by("periodo"))
            partidas = list(obra.expediente_tecnico.partidas.all())
            # Ritmo de ejecución respecto de lo programado: define si la obra
            # queda a tiempo, en riesgo o atrasada en el dashboard
            if obra.estado == ESTADO_CONCLUIDA:
                ritmo = Decimal(1)
            elif obra.estado == ESTADO_CON_RETRASO:
                ritmo = Decimal(random.choice(["0.60", "0.70", "0.78"]))
            else:
                ritmo = Decimal(random.choice(["1", "1", "0.97", "0.93", "0.85", "0.75"]))
            mes_paralizacion = random.randint(1, max(1, len(calendario) - 1)) if obra.estado == ESTADO_PARALIZADA else None

            fisico_prog = monto_prog = Decimal(0)
            ejecutado = devengado = Decimal(0)
            avance = None
            for i, periodo_cal in enumerate(calendario):
                if periodo_cal.periodo > hoy:
                    break
                fisico_prog += periodo_cal.avance_fisico_programado
                monto_prog += periodo_cal.monto_programado
                ultimo_mes = i == len(calendario) - 1
                if obra.estado == ESTADO_CONCLUIDA and ultimo_mes:
                    objetivo = Decimal(100)
                elif mes_paralizacion is not None and i >= mes_paralizacion:
                    objetivo = ejecutado  # obra paralizada: no hay avance nuevo
                else:
                    objetivo = min(Decimal(100), fisico_prog * ritmo)
                ejecutado = max(ejecutado, objetivo).quantize(Decimal("0.01"))
                ruido = Decimal(random.uniform(-0.04, 0.04))
                devengado = max(devengado, min(vigente, vigente * ejecutado / 100 * (1 + ruido))).quantize(Decimal("0.01"))

                avance = AvanceObra.objects.create(
                    obra=obra,
                    periodo=periodo_cal.periodo,
                    avance_fisico_programado_acum=min(fisico_prog, Decimal(100)),
                    avance_fisico_ejecutado_acum=ejecutado,
                    avance_financiero_programado_acum=min(Decimal(100), monto_prog * 100 / vigente).quantize(Decimal("0.01")),
                    avance_financiero_ejecutado_acum=min(Decimal(100), devengado * 100 / vigente).quantize(Decimal("0.01")),
                    monto_devengado_acum=devengado,
                    observaciones=fake.sentence(nb_words=15),
                    registrado_por=obra.residente,
                )
                if partidas:
                    # Metrados proporcionales al avance: reproducen el % físico registrado
                    for partida in partidas:
                        MetradoEjecutado.objects.create(
                            avance=avance, partida=partida,
                            metrado_acumulado=(partida.metrado * ejecutado / 100).quantize(Decimal("0.01")),
                        )

            if avance is None:
                continue
            evidencia = EvidenciaAvance(
                avance=avance,
                descripcion=f"Vista general del avance - {obra.codigo}",
            )
            # Se asigna el archivo sin confirmarlo a almacenamiento (patrón
            # recomendado por Django): así EvidenciaAvance.save() se encarga,
            # en una sola pasada, de comprimir la imagen (RNF-08) y de
            # aplicar el prefijo de "upload_to" una única vez.
            evidencia.imagen = imagen_evidencia(obra.codigo)
            evidencia.save()

    def _crear_valorizaciones(self, obras, usuarios):
        """Una valorización por obra, del último mes con avance registrado (RF-16, RF-19)."""
        estados = [e[0] for e in ESTADO_VALORIZACION_CHOICES]
        for obra in obras:
            ultimo = obra.avances.order_by("-periodo").first()
            if not ultimo:
                continue
            estado = random.choices(estados, weights=[0.3, 0.55, 0.15], k=1)[0]
            valorizacion = Valorizacion(
                obra=obra,
                numero=1,
                periodo=ultimo.periodo,
                monto=(ultimo.monto_devengado_acum * Decimal(random.randint(60, 100)) / 100).quantize(Decimal("0.01")),
                fecha_presentacion=min(date.today(), ultimo.periodo + timedelta(days=random.randint(28, 40))),
                estado=estado,
                observaciones_revision=fake.sentence(nb_words=10) if estado != ESTADO_REGISTRADA else "",
                registrado_por=obra.residente,
            )
            if estado != ESTADO_REGISTRADA:
                valorizacion.revisado_por = obra.supervisor
                valorizacion.fecha_revision = timezone.now() - timedelta(days=random.randint(1, 20))
            valorizacion.save()

    def _crear_informes(self, obras, usuarios):
        tipos = [t[0] for t in TIPO_INFORME_CHOICES]
        for obra in obras:
            ultimo = obra.avances.order_by("-periodo").first()
            if not ultimo:
                continue
            tipo = random.choice(tipos)
            autor = obra.residente if tipo == "RESIDENTE" else obra.supervisor
            InformeMensual.objects.create(
                obra=obra,
                periodo=ultimo.periodo,
                tipo=tipo,
                resumen=fake.paragraph(nb_sentences=5),
                elaborado_por=autor,
            )

    def _crear_calendario(self, obras):
        """
        Calendario de ejecución valorizado mensual (RF-20): el avance físico de
        los periodos suma 100 % y los montos suman el presupuesto asignado.
        """
        for obra in obras:
            meses = max(1, -(-obra.plazo_ejecucion_dias // 30))  # división redondeando hacia arriba
            pesos = [random.uniform(0.6, 1.4) for _ in range(meses)]
            total_pesos = sum(pesos)
            fisico_restante, monto_restante = Decimal(100), obra.presupuesto_asignado
            for i, peso in enumerate(pesos):
                ultimo = i == meses - 1
                fisico = fisico_restante if ultimo else Decimal(100 * peso / total_pesos).quantize(Decimal("0.01"))
                monto = monto_restante if ultimo else (obra.presupuesto_asignado * Decimal(peso / total_pesos)).quantize(Decimal("0.01"))
                fisico_restante -= fisico
                monto_restante -= monto
                CalendarioEjecucion.objects.create(
                    obra=obra,
                    periodo=_sumar_meses(obra.fecha_inicio.replace(day=1), i),
                    meta_programada=f"Avance programado del periodo {i + 1} - {obra.meta_fisica}",
                    monto_programado=monto,
                    avance_fisico_programado=fisico,
                    observaciones=fake.sentence(nb_words=8),
                )

    def _crear_ampliaciones(self, obras, usuarios):
        estados = [e[0] for e in ESTADO_AMPLIACION_CHOICES]
        for obra in obras:
            estado = random.choices(estados, weights=[0.2, 0.6, 0.2], k=1)[0]
            solicitados = random.choice([10, 15, 20, 30, 45, 60])
            fecha_solicitud = min(date.today(), obra.fecha_inicio + timedelta(days=random.randint(30, 120)))
            ampliacion = AmpliacionPlazo(
                obra=obra,
                numero=1,
                fecha_solicitud=fecha_solicitud,
                motivo=fake.sentence(nb_words=14),
                dias_solicitados=solicitados,
                estado=estado,
                registrado_por=usuarios[ROL_ADMIN][0],
            )
            if estado != "SOLICITADA":
                ampliacion.fecha_aprobacion = min(date.today(), fecha_solicitud + timedelta(days=5))
                ampliacion.resolucion = f"R.A. N° {random.randint(1, 300):03d}-{fecha_solicitud.year}-MDSR"
            if estado == ESTADO_APROBADA:
                ampliacion.dias_otorgados = random.choice([solicitados, solicitados, solicitados // 2 or 1])
            ampliacion.save()

    def _crear_adicionales(self, obras, usuarios):
        tipos = [t[0] for t in TIPO_ADICIONAL_DEDUCTIVO_CHOICES]
        estados = [e[0] for e in ESTADO_ADICIONAL_DEDUCTIVO_CHOICES]
        for obra in obras:
            tipo = random.choice(tipos)
            estado = random.choices(estados, weights=[0.25, 0.55, 0.2], k=1)[0]
            fecha_solicitud = min(date.today(), obra.fecha_inicio + timedelta(days=random.randint(40, 150)))
            adicional = AdicionalDeductivo(
                obra=obra,
                tipo=tipo,
                numero=1,
                monto=(obra.presupuesto_asignado * Decimal(random.randint(2, 15)) / 100).quantize(Decimal("0.01")),
                sustento=fake.sentence(nb_words=16),
                estado=estado,
                fecha_solicitud=fecha_solicitud,
                registrado_por=usuarios[ROL_ADMIN][0],
            )
            if estado != "SOLICITADO":
                adicional.fecha_aprobacion = min(date.today(), fecha_solicitud + timedelta(days=7))
                adicional.resolucion = f"R.A. N° {random.randint(1, 300):03d}-{fecha_solicitud.year}-MDSR"
            adicional.save()

    def _crear_documentos(self, obras, usuarios, tipos_documento):
        for obra in obras:
            tipo = random.choice(tipos_documento)
            documento = Documento(
                obra=obra,
                tipo_documento=tipo,
                nombre=f"{tipo.nombre} - {obra.codigo}",
                periodo=obra.fecha_inicio.replace(day=1),
                descripcion=fake.sentence(nb_words=10),
                subido_por=obra.residente,
            )
            documento.archivo.save(
                f"documento_{obra.pk}.pdf",
                pdf_simulado(tipo.nombre, f"Documento correspondiente a la obra {obra.codigo} - {obra.nombre}."),
                save=False,
            )
            documento.save()

    def _crear_bitacora(self, usuarios, total):
        todos_usuarios = [u for lista in usuarios.values() for u in lista]
        acciones = ["CREAR/ACTUALIZAR", "ELIMINAR"]
        modulos = ["obras", "avances", "valorizaciones", "calendario", "documentos", "usuarios"]
        for _ in range(total):
            Bitacora.objects.create(
                usuario=random.choice(todos_usuarios),
                accion=random.choices(acciones, weights=[0.9, 0.1], k=1)[0],
                modulo=random.choice(modulos),
                detalle="registro histórico de prueba",
                ruta=f"/{random.choice(modulos)}/",
                direccion_ip=f"192.168.{random.randint(0,10)}.{random.randint(2,250)}",
            )
