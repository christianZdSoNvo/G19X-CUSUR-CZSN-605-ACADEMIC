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

### 1. Programas necesarios

1. Instalar [Python 3.14](https://www.python.org/downloads/).
2. Instalar [MySQL 8.0](https://dev.mysql.com/downloads/) (y, si se desea, MySQL Workbench).
3. Instalar [Ollama](https://ollama.com/download) y descargar el modelo:
   ```
   ollama pull llama3:8b
   ```

### 2. Entorno de Python

En la carpeta del proyecto:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

o 

```
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Base de datos

1. Abrir `database/crear_bd.sql`, llenar la sección **"0. Valores de la instalación"** (contraseña del usuario de MySQL de la aplicación y datos del Administrador inicial) y ejecutarlo con **root**:
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

Copiar `.env.example` como `.env` y llenarlo:

```
DB_HOST=localhost
DB_USER=app_talentos
DB_PASSWORD=<la contraseña definida en crear_bd.sql>
DB_NAME=proyecto_talentos
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3:8b
```

El archivo `.env` nunca se sube al repositorio.

### 5. Contraseña del Administrador inicial

`crear_bd.sql` crea al Administrador sin contraseña (MySQL no puede calcular PBKDF2). Con el `.env` listo, se le asigna una temporal:

```
.venv\Scripts\python.exe reset_admin.py
```

El script muestra la contraseña temporal una sola vez; el sistema pide cambiarla en el primer inicio de sesión. Si se cargó `datos_actuales.sql`, este paso no hace falta.

## Ejecución

Con MySQL y Ollama en marcha:

```
.venv\Scripts\python.exe -m streamlit run app.py
```

El sistema abre en el navegador en `http://localhost:8501`. Solo se puede usar desde el mismo equipo.

En el primer inicio de sesión con el Administrador inicial, el sistema pide cambiar la contraseña temporal que dio `reset_admin.py`. La primera evaluación con IA puede tardar más, porque el modelo se carga en memoria (el sistema lo precarga al iniciar sesión).

## Alertas y notificaciones

Todas las notificaciones son **dentro del sistema**: aparecen en **Notificaciones y alertas** y en **Inicio**, con el número de pendientes junto al nombre de la sección en el menú. **El sistema no envía correos**: nadie recibe un aviso por correo electrónico.

Las alertas automáticas se configuran en **Notificaciones y alertas > Alertas** (el botón "Crear las alertas sugeridas" crea las cuatro reglas básicas) y se revisan en estos momentos:

| Regla | Cuándo se revisa |
|---|---|
| Cambio de la puntuación de IA o del nivel de potencial | Al guardar una nueva evaluación con IA del talento (se compara con la anterior) |
| Baja del desempeño previo | Al guardar la edición del talento |
| Días sin evaluar | Al iniciar sesión cualquier usuario (`alertas.revisar_sin_evaluar`); Streamlit no tiene tareas programadas, así que no se revisa mientras nadie entra al sistema |

Las reglas no son retroactivas: solo avisan de los cambios que ocurren después de crearlas. Un talento genera una sola alerta de "días sin evaluar" por regla hasta que se vuelve a evaluar.

## Usuarios de prueba

Para validar el sistema, al cargar `database/datos_actuales.sql` quedan disponibles estos usuarios, uno de cada cargo:

| Usuario | Contraseña inicial | Cargo | Área |
|---|---|---|---|
| `AdminRH` | `Admin123` | Administrador de RH | Recursos Humanos (acceso a todas las áreas) |
| `PruebaE` | `Prueba123` | Encargado de área | Finanzas |

En el primer inicio de sesión, el sistema pide cambiar la contraseña. Son cuentas solo para pruebas: en una instalación real conviene desactivarlas en **Gestión de usuarios**. Si solo se ejecuta `crear_bd.sql`, estos usuarios no existen y se entra con el Administrador inicial (ver el paso 5 de la instalación).

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

Se usó Claude Code (Anthropic) como asistente para escribir y comprobar código y pruebas; por eso aparece como coautor en los commits. El diseño, la documentación, las decisiones y las pruebas en el sistema las hizo el autor.

## Documentación

- El documento de requisitos del producto (PRD) y el alcance del MVP se entregan por separado; las referencias del código del tipo "PRD, 9.1" remiten a sus secciones.
- Los manuales de uso de cada sección se consultan dentro del sistema, en **Soporte**.
