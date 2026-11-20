# Sistema Web de Control y Seguimiento de Obras Públicas

Sistema web desarrollado para la tesis *"Desarrollo de un sistema web para
el control y seguimiento de obras públicas y evaluación de su calidad según
la norma ISO/IEC 25010 en la Municipalidad Distrital de Santa Rosa -
Ayacucho, 2026"*.

- **Lenguaje:** Python 3.11+
- **Framework:** Django 5.2 (arquitectura MVC: ver sección "Arquitectura")
- **Base de datos:** MySQL (compatible con el MySQL incluido en XAMPP)
- **Metodología de desarrollo:** Extreme Programming (XP)
- **Especificación de requisitos:** `docs/requisitos_funcionales_no_funcionales.docx` (RF-01 a RF-32, RNF-01 a RNF-23)

---

## 1. Requisitos previos

| Herramienta | Versión recomendada | Notas |
|---|---|---|
| XAMPP | 8.0 o superior | Se usa solo el módulo **MySQL** (y opcionalmente phpMyAdmin). No se necesita Apache ni PHP: Django trae su propio servidor de desarrollo. |
| Python | 3.11 o superior | [python.org/downloads](https://www.python.org/downloads/). En Windows, marcar "Add Python to PATH" durante la instalación. |
| Visual Studio Code | Última versión | Con la extensión **Python** (Microsoft) instalada. |
| Git (opcional) | Última versión | Solo si va a versionar el proyecto. |

---

## 2. Instalación paso a paso (Windows + XAMPP + VS Code)

### 2.1 Iniciar MySQL en XAMPP

1. Abra el **Panel de control de XAMPP**.
2. Inicie el módulo **MySQL** (botón "Start"). Déjelo corriendo en segundo plano.
3. (Opcional) Abra `http://localhost/phpmyadmin` para administrar la base de datos visualmente.

### 2.2 Crear la base de datos

Opción A — desde phpMyAdmin: cree una base de datos nueva llamada `obras_db`
con cotejamiento `utf8mb4_unicode_ci`.

Opción B — desde la terminal (si tiene `mysql` en el PATH):

```bash
mysql -u root -e "CREATE DATABASE obras_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Por defecto, XAMPP crea el usuario `root` **sin contraseña**, que es lo que
este proyecto asume de forma predeterminada (ver `.env.example`).

### 2.3 Abrir el proyecto en Visual Studio Code

1. Descomprima el proyecto en una carpeta, por ejemplo `C:\proyectos\sigop-obras`.
2. En VS Code: `Archivo -> Abrir carpeta...` y seleccione esa carpeta.
3. Abra una terminal integrada (`Ctrl + ñ` o `Terminal -> Nueva terminal`).

### 2.4 Crear el entorno virtual e instalar dependencias

```bash
# Windows (cmd o PowerShell)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Linux / Mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Cuando el entorno esté activo, VS Code normalmente detecta `venv/` y
pregunta si desea usarlo como intérprete de Python; responda que sí
(o selecciónelo manualmente con `Ctrl+Shift+P` → *Python: Select Interpreter*
→ elija el que está dentro de `venv`).

> **Nota sobre `mysqlclient` en Windows:** si la instalación de
> `mysqlclient` falla por no encontrar compiladores de C, descargue el
> *wheel* precompilado correspondiente a su versión de Python desde
> https://github.com/PyMySQL/mysqlclient/releases (o desde
> `https://www.lfd.uci.edu/~gohlke/pythonlibs/` si estuviera disponible) e
> instálelo con `pip install mysqlclient‑X.X.X‑cpXXX‑cpXXX‑win_amd64.whl`
> antes de volver a ejecutar `pip install -r requirements.txt`.

### 2.5 Configurar las variables de entorno

Copie `.env.example` a `.env` (mismo directorio que `manage.py`):

```bash
copy .env.example .env      REM Windows
cp .env.example .env        # Linux/Mac
```

Los valores por defecto de `.env.example` ya están pensados para XAMPP
(`DB_USER=root`, `DB_PASSWORD=` vacío, `DB_HOST=127.0.0.1`, `DB_PORT=3306`).
Ajústelos solo si su instalación de XAMPP usa credenciales distintas.

### 2.6 Elegir cómo cargar los datos: migraciones + seed, o importar el SQL ya generado

**Opción A (recomendada): generar la base de datos desde cero con Django**

```bash
python manage.py migrate
python manage.py seed_data
```

Esto crea todas las tablas y genera automáticamente **100 registros de
prueba por cada tabla de dominio** (usuarios, obras, avances,
valorizaciones, calendario, ampliaciones, adicionales/deductivos,
documentos y bitácora), con datos aleatorios pero realistas (Faker), además
de evidencias fotográficas y documentos PDF simulados.

Las únicas excepciones deliberadas al "100 por tabla" son las tablas de
catálogo/configuración, donde no tendría sentido: `TipoDocumento` (8 tipos
fijos: Expediente Técnico, Acta, Resolución, Contrato, etc.) y
`Configuracion` (1 solo registro, por diseño — ver `core/models.py`).

**Opción B (rápida): importar la base de datos ya poblada**

> Las carpetas `database/` y `media/` no se publican en el repositorio; se
> entregan aparte, en el paquete de despliegue. Si clonó el repositorio, use
> la opción A o copie ambas carpetas en la raíz del proyecto.

El archivo `database/obras_db_seed.sql` contiene un volcado completo de una
base de datos `obras_db` ya migrada y poblada con el comando `seed_data`
(estructura + 100 registros por tabla). Para usarla:

1. Cree la base de datos `obras_db` (paso 2.2).
2. Impórtela desde phpMyAdmin (pestaña "Importar") o por consola:
   ```bash
   mysql -u root obras_db < database/obras_db_seed.sql
   ```
3. La carpeta `media/` ya incluida en este paquete contiene las imágenes y
   PDF de ejemplo que ese volcado referencia, así que no es necesario
   generarlos de nuevo.
4. Aplique las migraciones posteriores al volcado (partidas del expediente,
   resolución de ampliaciones y adicionales, contratista, etc.):
   ```bash
   python manage.py migrate
   ```
   El volcado tiene un solo avance por obra. Para contar con el historial
   mensual que usan el calendario, la curva de evolución del dashboard y el
   informe mensual, se recomienda regenerar los datos con
   `python manage.py seed_data --flush`.

Con cualquiera de las dos opciones, al final tendrá la base de datos lista.
Si usó la Opción A, puede re-ejecutar `python manage.py seed_data --flush`
en cualquier momento para regenerar un nuevo conjunto aleatorio de datos de
prueba (por ejemplo si necesita "refrescar" la demo para la sustentación).

### 2.7 Ejecutar el servidor

```bash
python manage.py runserver
```

(En modo desarrollo, Django sirve automáticamente los archivos estáticos de
`static/` sin necesidad de `collectstatic`; ese comando solo es necesario si
más adelante despliega el proyecto en un servidor de producción.)

Abra `http://127.0.0.1:8000/` en el navegador. Será redirigido
automáticamente a la pantalla de inicio de sesión.

También puede iniciar el servidor directamente desde VS Code con
`F5` (configuración "Django: runserver" ya incluida en `.vscode/launch.json`).

---

## 3. Usuarios de acceso de prueba

El comando `seed_data` crea un usuario de acceso rápido por cada rol. La
contraseña es la misma para todos (cámbiela antes de usar el sistema en un
entorno real):

| Usuario | Rol | Contraseña |
|---|---|---|
| `admin001` | Administrador del sistema | `Clave12345` |
| `residente001` | Residente de obra | `Clave12345` |
| `supervisor001` | Supervisor / Inspector de obra | `Clave12345` |
| `apoyo001` | Personal administrativo de apoyo | `Clave12345` |
| `direccion001` | Alta dirección | `Clave12345` |

> Si la base se cargó desde `database/obras_db_seed.sql`, el usuario del
> personal administrativo de apoyo es `infraestructura001` (nombre anterior
> del rol; la migración `usuarios/0002_rol_apoyo` le asigna el rol nuevo).

Los roles corresponden a los actores del numeral 3.2 de la especificación:

| Rol | Puede registrar | Obras que ve |
|---|---|---|
| Administrador | Usuarios, obras, expediente técnico, calendario, ampliaciones, adicionales/deductivos, documentos (y en general todo) | Todas |
| Residente | Avance físico/financiero, evidencias (cuaderno de obra), valorizaciones, informe mensual | Solo las asignadas |
| Supervisor / Inspector | Revisión/aprobación de valorizaciones, informe mensual | Solo las asignadas |
| Personal administrativo de apoyo | Documentos del acervo documentario | Todas |
| Alta dirección | — (consulta del dashboard y reportes) | Todas |

El resto de usuarios generados (hasta completar 100) siguen el mismo patrón
de nombre de usuario (`residente002`, `supervisor017`, etc.) con la misma
contraseña.

El panel de administración de Django (gestión avanzada de cualquier tabla)
está disponible en `http://127.0.0.1:8000/admin/` con el usuario `admin001`.

---

## 4. Arquitectura: MVC (Django lo implementa como MVT)

Django organiza el código como **Modelo - Vista - Plantilla (MVT)**, que es
el mismo patrón MVC solicitado para el proyecto, con una diferencia de
nombres:

| Patrón MVC clásico | En este proyecto (Django) |
|---|---|
| **Modelo** (entidades, reglas de datos) | `*/models.py` de cada app (p. ej. `obras/models.py`) |
| **Controlador** (lógica de negocio, decide qué mostrar) | `*/views.py` de cada app — Django las llama "vistas", pero cumplen el rol de controlador |
| **Vista** (presentación al usuario) | `*/templates/**/*.html` — Django las llama "plantillas" |

Este mapeo está explicado también al inicio de `config/settings.py`.

### 4.1 Estructura de carpetas

```
config/              Configuración del proyecto Django (settings, urls raíz)
core/                 Roles, control de acceso, bitácora/auditoría (RNF-16),
                      utilidades (compresión de imágenes, generación de PDF),
                      comando de gestión seed_data.
usuarios/             Autenticación y gestión de usuarios y roles (RF-01 a RF-05)
obras/                Ficha técnica y expediente técnico de la obra (RF-06 a RF-10)
avances/              Avance físico/financiero y cuaderno de obra digital (RF-11 a RF-15)
valorizaciones/       Valorizaciones mensuales e informes (RF-16 a RF-19)
calendario/           Calendario de ejecución, ampliaciones de plazo,
                      adicionales y deductivos (RF-20 a RF-23)
documentos/           Acervo documentario (RF-24 a RF-26)
reportes/             Reportes consolidados PDF/Excel y dashboard dinámico (RF-27 a RF-32)
templates/            Plantilla base (base.html) y parciales compartidos
static/               CSS propio y librerías de terceros vendorizadas
                      (Bootstrap 5, Bootstrap Icons, Chart.js) — sin depender
                      de un CDN, por las condiciones de conectividad descritas
                      en el marco teórico de la tesis (RNF-08).
docs/                 Especificación de Requisitos Funcionales y No Funcionales
database/             Volcado SQL de ejemplo (obras_db_seed.sql)
media/                Archivos subidos (evidencias fotográficas, documentos, PDF)
```

### 4.2 Trazabilidad de requisitos

Cada módulo funcional del sistema corresponde a un bloque de la
especificación de requisitos (ver `docs/requisitos_funcionales_no_funcionales.docx`):

| Requisitos | Módulo (app Django) |
|---|---|
| RF-01 a RF-05 | `usuarios` |
| RF-06 a RF-10 | `obras` |
| RF-11 a RF-15 | `avances` |
| RF-16 a RF-19 | `valorizaciones` |
| RF-20 a RF-23 | `calendario` |
| RF-24 a RF-26 | `documentos` |
| RF-27 a RF-32 (incluye el **dashboard dinámico**) | `reportes` |
| RNF-01 a RNF-03 (adecuación funcional) | Verificado mediante pruebas unitarias (`*/tests.py`) y casos de prueba |
| RNF-04 a RNF-08 (eficiencia de desempeño) | Paginación, `select_related`, indicadores del dashboard y reportes con un número fijo de consultas agregadas (`reportes/services.py`), compresión de imágenes (`core/utils.py`), carga diferida de fotos, compresión gzip, índices de base de datos, PDF en procesos aparte y reutilizados mientras no cambien los datos, refresco del dashboard solo ante cambios |
| RNF-09 a RNF-14 (usabilidad) | Bootstrap 5 responsive, resumen de errores con campos resaltados y confirmación antes de operaciones críticas (`templates/base.html`), correlativos y fechas propuestos, consistencia visual (`static/css/estilos.css`) |
| RNF-15 a RNF-17 (seguridad) | Autenticación Django (contraseñas con PBKDF2 de 600 000 iteraciones), bloqueo tras intentos fallidos, validación del tipo y tamaño de los archivos, control de acceso por rol, bitácora (`core/middleware.py`), archivos subidos solo para usuarios autenticados y, en el caso del residente y el supervisor, solo los de sus obras (`core.views.ArchivoProtegidoView`) |
| RNF-18 a RNF-19 (fiabilidad) | Comando `respaldar_bd` (sección 7); validaciones de formulario y corrección del último avance |
| RNF-20 (compatibilidad) | Exportación PDF/Excel con estructura tipo INFOBRAS |
| RNF-21 a RNF-22 (mantenibilidad) | Arquitectura modular por app, código comentado |
| RNF-23 (portabilidad) | Configuración por variables de entorno (`.env`), sin dependencias nativas de SO en la generación de PDF |

---

## 5. Funcionalidades principales

- **Autenticación y roles** (administrador, personal de infraestructura,
  residente, supervisor/inspector, alta dirección) con permisos
  diferenciados por módulo.
- **Ficha técnica de obras** con expediente técnico vinculado, modalidad de
  ejecución, presupuesto y responsables.
- **Registro de avance físico y financiero** por periodo: el residente
  ingresa lo ejecutado (porcentaje físico o metrados por partida del
  expediente técnico, y monto devengado) y el sistema calcula el avance
  programado desde el calendario, el avance financiero sobre el presupuesto
  vigente, la desviación y el semáforo (a tiempo / en riesgo / atrasada).
  Incluye evidencia fotográfica (cuaderno de obra digital) y la corrección
  del último periodo registrado.
- **Valorizaciones mensuales** con flujo de revisión residente → supervisor
  (aprobar u observar; el residente corrige las observadas y vuelven a
  revisión) y exportación a PDF.
- **Informes mensuales** del residente y del supervisor que incorporan
  automáticamente el avance, las incidencias, las valorizaciones y las
  modificaciones contractuales del periodo; vista previa y PDF.
- **Calendario de ejecución valorizado**, ampliaciones de plazo y
  adicionales/deductivos con flujo de solicitud → resolución (aprobación o
  rechazo con N° de resolución) y recálculo automático del plazo, la fecha de
  culminación y el presupuesto vigentes.
- **Acervo documentario** con búsqueda general (todas las obras visibles para
  el usuario) y por obra, clasificado por tipo y periodo.
- **Dashboard dinámico** con indicadores clave (KPI), gráficos de barras
  coloreadas por semáforo, curva de evolución programado vs. ejecutado,
  alertas de obras en riesgo y filtros por obra, estado, unidad orgánica y
  periodo. Se actualiza solo cuando alguien registra información nueva.
- **Reportes consolidados** exportables en PDF y en Excel con una
  estructura de columnas compatible con la información exigida por INFOBRAS.
- **Bitácora de auditoría** de las operaciones críticas del sistema.

---

## 6. Pruebas automatizadas

```bash
python manage.py test
```

Incluye pruebas unitarias de: cálculo de presupuesto y plazo vigente
(`obras/tests.py`), cálculos y validaciones del registro de avance y
clasificación semafórica (`avances/tests.py`), flujo de aprobación de
ampliaciones y adicionales/deductivos y validaciones del calendario
(`calendario/tests.py`), flujo de revisión de valorizaciones e informe
mensual (`valorizaciones/tests.py`), búsqueda del acervo documentario
(`documentos/tests.py`), autenticación y control de acceso por rol
(`usuarios/tests.py`), dashboard dinámico con filtro por periodo y número de
consultas constante (`reportes/tests.py`), y respaldo de la base de datos y
protección de archivos (`core/tests.py`).

---

## 7. Respaldo de la base de datos (RNF-18)

```bash
python manage.py respaldar_bd
```

Genera en la carpeta `backups/` un archivo comprimido con fecha y hora
(`obras_db_AAAAMMDD_HHMMSS.sql.gz`) usando `mysqldump`, y conserva solo las
últimas 15 copias. Si `mysqldump` no está disponible, guarda los datos con
`dumpdata` de Django (`.json.gz`). Se configura en `.env`:

```
BACKUP_DIR=backups
BACKUP_CONSERVAR=15
MYSQLDUMP_PATH=C:/xampp/mysql/bin/mysqldump.exe
```

Para que sea **periódico**, prográmelo en el Programador de tareas de
Windows (acción: `C:\ruta\al\proyecto\venv\Scripts\python.exe`,
argumentos: `manage.py respaldar_bd`, iniciar en: la carpeta del proyecto),
por ejemplo todos los días a las 23:00. En Linux:
`0 23 * * * cd /ruta/proyecto && venv/bin/python manage.py respaldar_bd`.

Para restaurar una copia `.sql.gz`: descomprímala y ejecute
`mysql -u root obras_db < archivo.sql`.

---

## 8. Problemas frecuentes

- **`django.db.utils.OperationalError: (2002, ...)`**: MySQL no está
  corriendo. Verifique que el módulo MySQL de XAMPP esté iniciado.
- **`Access denied for user 'root'@'localhost'`**: su instalación de XAMPP
  tiene contraseña para `root`. Colóquela en `DB_PASSWORD` dentro de `.env`.
- **Error al instalar `mysqlclient` en Windows**: ver la nota en la sección
  2.4 sobre instalar el *wheel* precompilado.
- **Las imágenes/documentos no se ven tras importar `database/obras_db_seed.sql`**:
  verifique que la carpeta `media/` esté en la raíz del proyecto (junto a
  `manage.py`), tal como viene en este paquete.

## Despliegue en producción (RNF-23)

1. En `.env`, defina `DJANGO_DEBUG=False`, una `DJANGO_SECRET_KEY` propia, `DJANGO_ALLOWED_HOSTS` con la IP o el dominio del servidor y los datos de `EMAIL_*` para la recuperación de contraseña (RF-05).
2. Aplique las migraciones y prepare los archivos estáticos:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
3. Inicie el sistema con el servidor de producción:
   ```bash
   python manage.py servir --puerto 8000
   ```
4. Si se publica con certificado, agregue `DJANGO_HTTPS=True` (cookies seguras, HSTS y redirección a HTTPS) y compruebe la configuración con `python manage.py check --deploy`.
5. Programe el respaldo diario con `scripts\respaldo_programado.bat`; las instrucciones están al inicio de ese archivo (RNF-18).

Los errores del sistema quedan en `logs/sistema.log`.

## Diagrama de la base de datos

`docs/diagrama_bd.png` muestra todas las tablas con sus columnas; `docs/diagrama_bd_resumen.png`, solo las llaves y relaciones. Sus fuentes (`docs/*.mmd`, formato Mermaid) se regeneran desde los modelos:

```bash
python manage.py diagrama_bd
python manage.py diagrama_bd --resumen
```

## Estándares de código y pruebas (RNF-22)

```bash
pip install -r requirements-dev.txt
ruff check .
coverage run manage.py test
coverage report
```
