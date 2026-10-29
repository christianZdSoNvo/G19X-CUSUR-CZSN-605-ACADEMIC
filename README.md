# TalentOS (Talent Overview System)

Sistema de Identificación de Talento de Alto Potencial. Registra a los talentos de la organización, los evalúa con inteligencia artificial local (Llama 3 8B mediante Ollama), los clasifica en la matriz 9-box y presenta paneles analíticos, historial, reportes y notificaciones para el área de Recursos Humanos.

Todo el sistema (interfaz, base de datos y modelo de IA) se instala y se ejecuta en un solo equipo: ningún dato sale a Internet.

Contexto: PluriOne (HRTech / People Analytics).
Autor: Christian Zaid Solano Navarro.

## Funciones principales

| Sección | Qué hace |
|---|---|
| Inicio de sesión | Usuario y contraseña con política de seguridad, bloqueo tras intentos fallidos, cambio obligatorio de contraseña temporal y cierre por inactividad. |
| Talentos | Alta, edición, baja lógica y reactivación de talentos, con foto de perfil e indicadores (desempeño, competencias, capacitación, experiencia, objetivos y liderazgo). |
| Evaluación con IA | Llama 3 evalúa seis criterios, asigna una puntuación de 0 a 100, el nivel de potencial y un reporte con sugerencias; el sistema calcula la clasificación 9-box. |
| Paneles analíticos | Indicadores, distribución por nivel, matriz 9-box, promedio por área, histograma, evolución mensual y radar, con filtros y detalle al hacer clic. |
| Historial y evolución | Línea de tiempo de cada talento con sus evaluaciones y eventos. |
| Reportes | Reporte individual y general en PDF y Excel (con respaldo en texto si falla la exportación). |
| Notificaciones y alertas | Mensajes entre usuarios y alertas automáticas configurables (cambios de puntuación, nivel o desempeño y días sin evaluar). |
| Configuración | Gestión de usuarios, parámetros del sistema, manuales por cargo, bitácora de acciones, tema claro u oscuro y contacto de soporte. |

### Cargos

- **Administrador de RH:** acceso completo a todas las áreas y funciones.
- **Encargado de área:** consulta solo los talentos de su área y solicita correcciones o reevaluaciones al Administrador.

## Tecnologías

- **Python 3.14** con **Streamlit** (interfaz), **pandas**, **Plotly** (gráficas), **fpdf2** (PDF), **openpyxl** (Excel) y **Pillow** (fotos).
- **MySQL 8.0.17 o superior** (base de datos `proyecto_talentos`, conexión cifrada con SSL).
- **Ollama** con el modelo **llama3:8b**.
- **pytest** para las pruebas automáticas.

### Equipo recomendado

16 GB de RAM, procesador de 4 núcleos o más y, de preferencia, una tarjeta de video con al menos 4 GB. El modelo de IA ocupa cerca de 5 GB en disco.

### Equipos con menos recursos

En un equipo sin tarjeta de video o con menos de 16 GB de RAM se puede usar **llama3.2:3b** (cerca de 2 GB en disco):

```
ollama pull llama3.2:3b
```

y en el `.env` poner `OLLAMA_MODEL=llama3.2:3b`. No hay que cambiar nada más: el sistema usa el mismo prompt y la misma validación.

Se comparó con llama3:8b evaluando los mismos 10 talentos de prueba en el equipo de desarrollo:

| | llama3.2:3b | llama3:8b |
|---|---|---|
| Respuestas válidas al primer intento | 9 de 10 | 10 de 10 |
| Respuestas válidas con reintentos | 10 de 10 | 10 de 10 |
| Tiempo por evaluación | 8 a 14 s | 52 a 80 s |
| Mismo nivel de potencial que llama3:8b | 10 de 10 | — |
| Mismo nivel por criterio que llama3:8b | 34 de 60 | — |

Es más rápido y da el mismo nivel de potencial, pero sus niveles por criterio son menos precisos, por lo que llama3:8b sigue siendo el modelo recomendado. En un equipo sin tarjeta de video las evaluaciones tardan más; si pasan del tiempo máximo (90 s por omisión), se puede subir en **Parámetros del sistema**.

**Si Ollama no está instalado o no está en marcha**, el resto del sistema funciona con normalidad (talentos, paneles, historial, reportes, notificaciones y configuración); solo la evaluación con IA muestra un error:

| Código | Cuándo aparece | Qué hacer |
|---|---|---|
| E-101 | Ollama no responde o el modelo de `OLLAMA_MODEL` no está descargado. No gasta intento. | Iniciar Ollama o descargar el modelo con `ollama pull` y volver a evaluar. |
| E-102 | El modelo tardó más que el tiempo máximo. Gasta un intento. | Volver a intentar o subir el tiempo máximo en **Parámetros del sistema**. |
| E-103 | El modelo no devolvió una evaluación válida en ninguno de los intentos disponibles. | Intentar más tarde o al día siguiente. |
| E-104 | El talento ya usó todas sus evaluaciones del día (3 por omisión). | Esperar al día siguiente o cambiar el límite en **Parámetros del sistema**. |

## Instalación

Las instrucciones son para Windows 10 u 11.

### 0. Obtener el código

- **Con Git:** `git clone <URL del repositorio>`.
- **Sin Git:** en GitHub, **Code > Download ZIP** y descomprimirlo. El ZIP crea una subcarpeta con el nombre del repositorio; esa subcarpeta es la del proyecto (o se puede mover su contenido a otra carpeta).

En este README, **la carpeta del proyecto** es la que contiene `app.py`.

**Abrir una terminal en la carpeta del proyecto:** todos los comandos de la instalación se escriben en el **Símbolo del sistema (CMD)**, no en PowerShell (PowerShell no acepta el `<` de los comandos de `mysql`). La forma más sencilla de abrirlo: en el Explorador de archivos, entrar a la carpeta del proyecto, escribir `cmd` en la barra de direcciones y presionar Enter. Los comandos se escriben **uno por uno**, esperando a que termine cada uno antes de escribir el siguiente.

### 1. Programas necesarios

1. **Python 3.14.** En la página de [Python 3.14.9](https://www.python.org/downloads/release/python-3149/) (o cualquier 3.14.x en [la lista de versiones](https://www.python.org/downloads/windows/); la primera de la página general de descargas puede ser una versión más nueva), descargar **Windows installer (64-bit)**. En el instalador, marcar **"Add python.exe to PATH"** y elegir **Install Now**. Comprobar en una terminal nueva:
   ```
   py -3.14 --version
   ```
   Debe responder `Python 3.14.x`. **Solo se probó con Python 3.14** (3.14.7 en el equipo de desarrollo y 3.14.9 en una instalación limpia); no se probó con 3.12 ni 3.13.
2. **MySQL 8.0.** En [MySQL Installer](https://dev.mysql.com/downloads/installer/), descargar el instalador más ligero (**mysql-installer-web-community**, unos 2 MB; dice "32-bit", pero instala el servidor de 64 bits). La página ofrece iniciar sesión con una cuenta de Oracle: no hace falta, basta con **"No thanks, just start my download"**.
   - Tipo de instalación: **Server only** (MySQL Workbench es opcional).
   - En la configuración se pueden dejar los valores recomendados: puerto **3306**, autenticación con contraseña fuerte, servicio de Windows **MySQL80** que arranca con Windows. Anotar la **contraseña de root**.
   - Agregar MySQL al PATH para poder usar el comando `mysql`: buscar «variables de entorno» en el menú Inicio > **Variables de entorno** > en *Variables del sistema* elegir **Path** > **Editar** > **Nuevo** > `C:\Program Files\MySQL\MySQL Server 8.0\bin` > Aceptar. Después, abrir una terminal **nueva** y comprobar:
     ```
     mysql --version
     ```
3. **Ollama.** Instalar [Ollama](https://ollama.com/download) con el instalador para Windows y, en una terminal nueva, descargar el modelo:
   ```
   ollama pull llama3:8b
   ```
   **En un equipo sin tarjeta de video o con menos de 16 GB de RAM**, descargar en su lugar el modelo ligero (ver [Equipos con menos recursos](#equipos-con-menos-recursos)):
   ```
   ollama pull llama3.2:3b
   ```

### 2. Entorno de Python

En la carpeta del proyecto, uno por uno:

```
py -3.14 -m venv .venv
```

```
.venv\Scripts\python.exe --version
```

Debe responder `Python 3.14.x`. Si no, borrar la carpeta `.venv` y revisar la instalación de Python.

```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

La instalación de los paquetes tarda unos minutos y termina con `Successfully installed ...`.

### 3. Base de datos

Los comandos `mysql ... < archivo.sql` de este paso se escriben en **CMD**; en PowerShell fallan con *«El operador '<' está reservado para uso futuro»*.

1. Abrir `database/crear_bd.sql` con un editor de texto y llenar la sección **"0. Valores de la instalación"**:
   - `@contrasena_app`: una contraseña **nueva**, solo para el usuario de MySQL `app_talentos` que usa el sistema. Debe ser **distinta de la de root**; es la que después va en `DB_PASSWORD` del `.env`.
   - Los datos del Administrador inicial (nombre, usuario, correo y teléfono).

   Guardarlo y ejecutarlo con **root** (pide la contraseña de root):
   ```
   mysql -u root -p < database\crear_bd.sql
   ```
   Crea la base de datos, las 10 tablas, el usuario de MySQL `app_talentos` con privilegios mínimos, la configuración inicial, el Administrador inicial y los manuales (solo texto).
2. **(Opcional) Cargar los datos de prueba** (los dos usuarios de prueba, 60 talentos ficticios con sus evaluaciones, notificaciones, alertas y bitácora; 0.2 MB):
   ```
   mysql -u root -p < database\datos_actuales.sql
   ```
   Reemplaza al Administrador inicial por los [usuarios de prueba](#usuarios-de-prueba) y conserva los manuales de `crear_bd.sql`. No contiene datos de personas reales.
3. **(Opcional) Cargar los manuales con imágenes** (los manuales de cada cargo con sus capturas anotadas; 8.7 MB), después del paso 2:
   ```
   mysql -u root -p < database\imagenes_manuales.sql
   ```
   Reemplaza los manuales de solo texto. Necesita los usuarios de prueba del paso 2. En MySQL Workbench conviene usar **File > Run SQL Script**, porque el archivo es grande.

Los scripts `actualizar_*.sql` solo sirven para actualizar una base instalada con una versión anterior; en una instalación nueva no se ejecutan.

### 4. Archivo `.env`

Copiar `.env.example` como `.env`, en la misma carpeta. En CMD:

```
copy .env.example .env
```

Si se hace con el Bloc de notas (**Guardar como**), hay que escribir el nombre `.env` y cambiar el tipo a **Todos los archivos**; si no, queda como `.env.txt` y el sistema no lo encuentra.

Después, abrir `.env` y llenarlo:

```
DB_HOST=localhost
DB_USER=app_talentos
DB_PASSWORD=<la contraseña de @contrasena_app en crear_bd.sql>
DB_NAME=proyecto_talentos
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3:8b
```

**En un equipo sin tarjeta de video o con menos de 16 GB de RAM**, poner `OLLAMA_MODEL=llama3.2:3b` (el modelo descargado en el paso 1).

El archivo `.env` nunca se sube al repositorio.

### 5. Contraseña del Administrador inicial

**Si se cargó `datos_actuales.sql`, este paso no hace falta:** se entra con los [usuarios de prueba](#usuarios-de-prueba).

`crear_bd.sql` crea al Administrador sin contraseña (MySQL no puede calcular PBKDF2). Con el `.env` listo, se le asigna una temporal:

```
.venv\Scripts\python.exe reset_admin.py
```

El script muestra la contraseña temporal una sola vez; el sistema pide cambiarla en el primer inicio de sesión.

## Ejecución

MySQL y Ollama deben estar en marcha. Normalmente arrancan solos con Windows; para comprobarlo:

- **MySQL:** en la aplicación **Servicios** de Windows, el servicio **MySQL80** debe decir *En ejecución* (si no, clic derecho > **Iniciar**).
- **Ollama:** su ícono (una llama) debe aparecer junto al reloj, en la barra de tareas (si no, abrir **Ollama** desde el menú Inicio).

En la carpeta del proyecto:

```
.venv\Scripts\python.exe -m streamlit run app.py
```

El sistema abre en el navegador en `http://localhost:8501`. Solo se puede usar desde el mismo equipo.

En el primer inicio de sesión con el Administrador inicial, el sistema pide cambiar la contraseña temporal que dio `reset_admin.py`. La primera evaluación con IA puede tardar más, porque el modelo se carga en memoria (el sistema lo precarga al iniciar sesión).

## Alertas y notificaciones

Todas las notificaciones son **dentro del sistema**: aparecen en **Notificaciones y alertas** y en **Inicio**, con el número de pendientes junto al nombre de la sección en el menú. **El sistema no envía correos**: nadie recibe un aviso por correo electrónico.

Las alertas automáticas se configuran en **Notificaciones y alertas > Alertas**. Cuando todavía no hay ninguna alerta, aparece el botón "Crear las alertas sugeridas", que crea las cuatro reglas básicas; con `datos_actuales.sql` ya hay 2 alertas de prueba, así que el botón no se muestra.

Se revisan en estos momentos:

| Regla | Cuándo se revisa |
|---|---|
| Cambio de la puntuación de IA o del nivel de potencial | Al guardar una nueva evaluación con IA del talento (se compara con la anterior) |
| Baja del desempeño previo | Al guardar la edición del talento |
| Días sin evaluar | Al iniciar sesión cualquier usuario (`alertas.revisar_sin_evaluar`); Streamlit no tiene tareas programadas, así que no se revisa mientras nadie entra al sistema |

Las reglas de cambio de puntuación, de nivel de potencial y de baja del desempeño no son retroactivas: solo avisan de los cambios que ocurren después de crearlas. La de días sin evaluar sí incluye a los talentos que ya llevaban esos días sin evaluación al crearla. Un talento genera una sola alerta de "días sin evaluar" por regla hasta que se vuelve a evaluar.

## Usuarios de prueba

Para validar el sistema, al cargar `database/datos_actuales.sql` quedan disponibles estos usuarios, uno de cada cargo:

| Usuario | Contraseña inicial | Cargo | Área |
|---|---|---|---|
| `AdminRH` | `Admin123` | Administrador de RH | Recursos Humanos (acceso a todas las áreas) |
| `PruebaE` | `Prueba123` | Encargado de área | Finanzas |

En el primer inicio de sesión, el sistema pide cambiar la contraseña. Son cuentas solo para pruebas: en una instalación real conviene desactivarlas en **Gestión de usuarios**. Si solo se ejecuta `crear_bd.sql`, estos usuarios no existen y se entra con el Administrador inicial (ver el paso 5 de la instalación).

## Recorrido de prueba

Para comprobar en unos minutos que el sistema funciona, con `datos_actuales.sql` (y, de preferencia, `imagenes_manuales.sql`) cargados y el sistema en marcha:

| # | Cuenta | Qué hacer | Qué se espera ver |
|---|---|---|---|
| 1 | `AdminRH` | Iniciar sesión con `Admin123`. | El sistema pide cambiar la contraseña; con la nueva se entra a **Inicio**, con los accesos a cada sección y el aviso de notificaciones pendientes. |
| 2 | `AdminRH` | Abrir **Talentos** y elegir un talento de la lista. | Aparecen los 60 talentos de prueba; la pestaña **Datos del talento** muestra sus datos e indicadores. |
| 3 | `AdminRH` | En la pestaña **Evaluación con IA**, pulsar **Evaluar con IA**. | Tras unos segundos (cerca de 1 minuto en un equipo sin tarjeta de video) aparecen el nivel de potencial, la puntuación, la tabla de criterios con la **Clasificación 9-box** y el reporte con sugerencias. Si Ollama no está en marcha, aparece **E-101** y el resto del sistema sigue funcionando. |
| 4 | `AdminRH` | Abrir **Historial y evolución** y buscar el mismo talento. | Su línea de tiempo incluye la evaluación del paso 3. |
| 5 | `AdminRH` | Abrir **Paneles analíticos**, hacer clic en una celda de la matriz 9-box, cambiar un filtro y pulsar **Limpiar filtros**. | Se ven las tarjetas y las gráficas; el clic muestra la lista de talentos de esa celda; los filtros cambian los datos y **Limpiar filtros** los regresa. |
| 6 | `AdminRH` | En **Reportes > Reporte individual**, elegir el talento evaluado y pulsar **Generar PDF** y **Generar Excel**; repetir en **Reporte general**. | Los cuatro archivos se descargan y se abren; el PDF individual trae la evaluación del paso 3 (elegida en **Evaluación del PDF**). |
| 7 | `AdminRH` | Abrir **Notificaciones y alertas**: pestañas **Bandeja** y **Alertas**. | La bandeja muestra las notificaciones de prueba; en **Alertas** están las 2 alertas de prueba (el botón "Crear las alertas sugeridas" no aparece porque ya hay alertas). |
| 8 | `AdminRH` | Abrir **Gestión de usuarios**, **Parámetros del sistema**, **Bitácora** y **Manuales**. | Se ven `AdminRH` y `PruebaE`, los parámetros con sus valores, los inicios de sesión y la evaluación del día en la bitácora, y los manuales (con imágenes si se cargó `imagenes_manuales.sql`). Cerrar sesión. |
| 9 | `PruebaE` | Iniciar sesión con `Prueba123`. | El sistema pide cambiar la contraseña. El menú **no** muestra Gestión de usuarios, Parámetros del sistema ni Bitácora. |
| 10 | `PruebaE` | Abrir **Talentos** y elegir un talento. | Solo aparecen talentos de **Finanzas**, con el filtro de área fijo; la ficha es de solo consulta (sin editar ni **Evaluar con IA**). Al final de **Datos del talento** están **Solicitar corrección de datos** y **Solicitar reevaluación con IA**. |
| 11 | `PruebaE` | Abrir **Paneles analíticos** e **Historial y evolución**. | Solo muestran datos de Finanzas. |
| 12 | `PruebaE` | Abrir **Manuales** y **Notificaciones y alertas > Nueva notificación**. | Solo aparecen los manuales del Encargado; puede escribir al Administrador de prueba. |

## Limitaciones conocidas

Lo que el sistema no hace, o hace solo con ciertas condiciones; no son errores.

- **Solo se usa desde el mismo equipo** (`http://localhost:8501`), como se estableció en el diseño.
- **No envía correos**: las notificaciones y alertas solo aparecen dentro del sistema.
- **«Días sin evaluar» se revisa al iniciar sesión**, no a una hora fija, como se estableció en el diseño.
- **Las alertas de cambio de puntuación, de nivel de potencial y de baja del desempeño no son retroactivas**: solo avisan de los cambios que ocurren después de crear la regla.
- **3 evaluaciones con IA por talento al día**; se cambia en **Parámetros del sistema**.
- **Sin tarjeta de video, cada evaluación tarda cerca de 1 minuto**; si pasa del tiempo máximo (90 s), se sube en **Parámetros del sistema**.
- **Un usuario desactivado con la sesión abierta sigue dentro** hasta que cierra sesión o pasan 30 minutos sin actividad.
- **Solo se probó en Windows** (10 y 11) **con Python 3.14**.

Ideas que quedaron pendientes:

- Importar talentos desde un archivo de Excel (hoy se capturan uno por uno en **Talentos**).
- Que el Administrador pueda editar desde **Configuración** las partes del prompt de la IA que no afectan el formato de la respuesta (las descripciones de los criterios e indicaciones adicionales de RH), con la posibilidad de restaurar el original.
- Reordenar las imágenes de un manual y agregar un pie de texto a cada una (hoy se muestran en el orden en que se subieron).
- Revisar en cada acción si la cuenta sigue activa, para cerrar al momento la sesión de un usuario desactivado.

## Scripts de apoyo

| Script | Uso |
|---|---|
| `reset_admin.py` | Asigna la primera contraseña del Administrador inicial o restablece la de un Administrador desde el equipo: `.venv\Scripts\python.exe reset_admin.py [--usuario X]` |
| `datos_ejemplo.py` | Genera talentos y evaluaciones de ejemplo: `vista` (Excel sin tocar la base), `cargar` o `borrar` |
| `exportar_datos.py` | Vuelve a generar `database/datos_actuales.sql` y `database/imagenes_manuales.sql` a partir de la base, solo con datos de prueba: quita los usuarios que no son de prueba, los talentos que no son de `datos_ejemplo.py` y todo lo que los mencione |

## Pruebas

```
.venv\Scripts\python.exe -m pytest
```

Las pruebas que usan MySQL trabajan dentro de una transacción que se deshace al final, por lo que no dejan registros. Ollama se simula, así que no hace falta que esté en marcha.

## Estructura del proyecto

```
app.py                 Entrada: inicio de sesión, menú por cargo y manejo de errores
paginas/               Pantallas del sistema (una por sección)
backend/               Lógica: base de datos, seguridad, permisos, IA, reportes, alertas, etc.
database/              Scripts SQL de instalación, actualización y datos
recursos/              Logo, ícono y avatar
tests/                 Pruebas automáticas (pytest)
logs/                  Registro de errores del sistema (sistema.log)
.streamlit/config.toml Servidor local y tema de colores
```

## Códigos de error

Cuando ocurre un error, el sistema muestra un mensaje con un código copiable para soporte:

| Código | Significado |
|---|---|
| E-001 / E-002 | Sin conexión con la base de datos / error de configuración |
| E-003 / E-004 | Datos no válidos / registro duplicado |
| E-101 a E-104 | IA no disponible, tiempo agotado, respuesta no válida o límite de evaluaciones |
| E-201 / E-202 | No se pudo generar el PDF o el Excel (se entrega un archivo de texto) |
| E-301 a E-304 | Credenciales incorrectas, cuenta bloqueada, sesión expirada o sin permiso |
| E-401 / E-402 | Sin manuales disponibles / imagen no válida (PNG o JPG de máximo 5 MB) |

## IA usada en el desarrollo

Se usó Claude Code (Anthropic) como asistente para escribir código, pruebas y documentación (este README, la bitácora de [docs/instalacion_limpia.md](docs/instalacion_limpia.md) y los documentos del proyecto); por eso aparece como coautor en los commits. El autor tomó las decisiones de diseño y de alcance, revisó lo que generó la IA antes de cada commit y probó el sistema por su cuenta: usó cada sección con las dos cuentas de prueba, hizo la instalación limpia en otro equipo siguiendo solo este README, de donde salió el «Recorrido de prueba».

## Documentación

- El documento de requisitos del producto (PRD) y el alcance del MVP se entregan por separado; las referencias del código del tipo "PRD, 9.1" remiten a sus secciones.
- Los manuales de uso de cada sección se consultan dentro del sistema, en **Soporte**.
