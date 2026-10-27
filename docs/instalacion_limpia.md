# Bitácora de instalación limpia

Prueba de instalación de TalentOS en un equipo distinto al de desarrollo, siguiendo
solo el `README.md` del repositorio. En cada paso se anota el resultado (OK o FALLA,
con el mensaje exacto), lo que hubo que hacer para seguir y el tiempo aproximado.

- **Fecha:** 27/10/2026
- **Repositorio:** https://github.com/christianZdSoNvo/G19X-CUSUR-CZSN-605-ACADEMIC
- **Commit probado:** `cce4fda` (ZIP de la rama `main` descargado ese día)
- **Carpeta de instalación:** `C:\prueba-talentos`

## 0. Equipo de prueba

| Característica | Valor |
|---|---|
| Sistema operativo | Windows 10 Pro for Workstations |
| RAM | 16 GB |
| Procesador | AMD Ryzen 3 5300U with Radeon Graphics, 2.60 GHz |
| Tarjeta de video | Sin tarjeta dedicada (gráficos Radeon integrados al procesador) |
| Espacio libre | 724 GB |
| Programas previos | Ninguno: Python, MySQL, Ollama y Git se instalan desde cero |

Por no tener tarjeta de video, según el README («Equipos con menos recursos») corresponde
usar el modelo **llama3.2:3b**.

## 1. Obtener el código

**Resultado:** OK, con un ajuste manual.

- Se usó la opción sin Git: en GitHub, **Code > Download ZIP** y descomprimir.
- **El README no dice cómo obtener el código** (ni con `git clone` ni con el ZIP).
- Al descomprimir, los archivos quedaron en una subcarpeta
  (`C:\prueba-talentos\G19X-CUSUR-CZSN-605-ACADEMIC-main\`). Para seguir, se movió su
  contenido a `C:\prueba-talentos`. El README tampoco aclara cuál es «la carpeta del
  proyecto» (la que contiene `app.py`).

## 2. Programas necesarios

### 2.1 Python

**Resultado:** OK con `py`; FALLA con `python`. Tiempo aproximado: 5 minutos de descarga.

- El enlace «Python 3.14» del README lleva a la página general de descargas, donde lo
  primero que aparece es la versión más reciente (3.15.2). Hubo que bajar en la lista,
  abrir **Python 3.14.9** y, en su página, buscar **Windows installer (64-bit)**.
- Versión instalada: **3.14.9**.
- El instalador muestra la casilla **"Add python.exe to PATH"**; **no se marcó** porque el
  README no dice nada de ella.
- Se eligió **Install Now** (el README tampoco indica qué opción elegir). Al final solo
  apareció un aviso preguntando si se era nuevo en Python.
- Comprobación en CMD:
  - `python --version` → *«No se encontró Python; ejecuta sin argumentos para instalar
    desde Microsoft Store o deshabilita este acceso directo en Configuración > Administrar
    alias de ejecución de la aplicación.»* (Python no quedó en el PATH por no marcar la
    casilla; el mensaje viene del alias de la Microsoft Store.)
  - `py --version` → `Python 3.14.9`.

### 2.2 MySQL

**Resultado:** OK, con un ajuste manual (PATH). Tiempo aproximado: 15 minutos.

- El enlace del README lleva a la página general de descargas de MySQL, donde
  **MySQL Installer for Windows** aparece junto con otras opciones; el README no dice cuál
  elegir.
- Se descargó **MySQL Installer 8.0.46**, archivo «Windows (x86, 32-bit), MSI Installer» de
  2.1 MB (el más ligero; el README no dice cuál de los dos instaladores usar).
- La página ofrece iniciar sesión con una cuenta de Oracle, pero es opcional: abajo está
  **«No thanks, just start my download»**. El README no lo menciona.
- Tipo de instalación: **Server only** (el README no indica cuál elegir). No se instaló
  MySQL Workbench.
- Pantallas de configuración: descarga, instalación, puerto **3306**, método de
  autenticación (se dejó la opción recomendada de contraseña fuerte), contraseña de root,
  servicio de Windows **MySQL80** (arranca con Windows), permisos del servidor de archivos
  (se dejó la primera opción, acceso completo al usuario), aplicación de la configuración y
  pantalla final.
- `mysql --version` **no se reconocía**: hubo que agregar a la variable de entorno PATH la
  carpeta `C:\Program Files\MySQL\MySQL Server 8.0\bin` (Buscar «variables de entorno» >
  Variables de entorno > Path > Nuevo) y abrir una terminal nueva. El README no lo
  menciona. Después respondió
  `mysql  Ver 8.0.46 for Win64 on x86_64 (MySQL Community Server - GPL)`.

### 2.3 Ollama y el modelo

**Resultado:** OK. Tiempo aproximado: 20 minutos (descarga e instalación de Ollama) +
8 minutos (modelo).

- El enlace del README lleva directo a la descarga para Windows. La página ofrece instalar
  desde la terminal o con el instalador; se usó el instalador.
- La instalación no pidió nada especial y, al terminar, Ollama quedó abierto.
- Versión: `ollama version is 0.40.11`. `ollama --version` y `ollama list` funcionaron en
  una terminal nueva sin tocar el PATH.
- Modelo: **llama3.2:3b** (equipo sin tarjeta de video), sin errores. El README lo indica en
  «Equipos con menos recursos», pero el paso 1 de la instalación solo muestra
  `ollama pull llama3:8b`: **convendría un recordatorio ahí** para los equipos sin tarjeta
  de video o con menos de 16 GB.

## 3. Entorno de Python

**Resultado:** FALLA con `python`; OK con `py`. Tiempo aproximado: 10 minutos (paquetes).

- Para llegar a la carpeta del proyecto se usó `cd` en CMD. También se probó abrir PowerShell
  en la carpeta con Shift + clic derecho. El README no dice cómo abrir una terminal en la
  carpeta del proyecto.
- Primera opción del README (`python -m venv .venv` + `pip install`), en PowerShell:
  ```
  No se encontró Python; ejecuta sin argumentos para instalar desde
  Microsoft Store o deshabilita este acceso directo en Configuración >
  Administrar alias de ejecución de la aplicación.
  .venv\Scripts\python.exe : El módulo '.venv' no pudo cargarse. Para
  obtener más información, ejecute 'Import-Module
  .venv'.
  ...
      + FullyQualifiedErrorId : CouldNotAutoLoadModule
  ```
  El primer comando falla porque Python no está en el PATH (ver 2.1). El segundo error
  aparece porque, al pegar las dos líneas juntas, `pip install` se ejecuta aunque el entorno
  `.venv` no se haya creado. En la consola los acentos salieron como «¾».
- Segunda opción del README (`py -m venv .venv` + `pip install`): **OK** en PowerShell
  (también funciona en CMD).
- `.venv\Scripts\python.exe --version` → `Python 3.14.9`.
- `pip install -r requirements.txt` terminó sin errores; última línea:
  `Successfully installed ...`.

## 4. Base de datos

**Resultado:** FALLA en PowerShell; OK en CMD. Tiempo aproximado: 1 minuto
(`crear_bd.sql`) y menos de 5 segundos cada uno de los otros dos scripts.

- `crear_bd.sql` se abrió con VS Code. Los 5 valores de la sección **"0. Valores de la
  instalación"** quedaron claros, salvo `@contrasena_app`: puede confundirse con la
  contraseña de root definida al instalar MySQL. Usar la misma funciona, pero resta
  seguridad; el README debería decir que es una contraseña **nueva**, solo para el usuario
  `app_talentos`, y que es la que después va en el `.env`.
- `mysql -u root -p < database\crear_bd.sql` en **PowerShell** (tal como dice el README):
  ```
  En línea: 1 Carácter: 18
  + mysql -u root -p < database\crear_bd.sql
  +                  ~
  El operador '<' está reservado para uso futuro.
      + CategoryInfo          : ParserError: (:) [],
  ParentContainsErrorRecordException
      + FullyQualifiedErrorId : RedirectionNotSupported
  ```
  PowerShell no admite `<`; el README no dice que estos comandos son para CMD.
- El mismo comando en **CMD**: pidió la contraseña de root y terminó sin errores, mostrando
  el resultado de la creación de la base de datos.
- `datos_actuales.sql` e `imagenes_manuales.sql` en CMD: sin errores. Al terminar,
  `datos_actuales.sql` mostró 2 usuarios y 60 talentos, como se esperaba.

## 5. Archivo `.env`

**Resultado:** OK.

- Para copiarlo se abrió `.env.example` en un editor de texto y, con **Guardar como**, se
  borró el nombre, se escribió `.env` y se cambió el tipo de «Documentos de texto (*.txt)»
  a «Todos los archivos». En la carpeta quedaron `.env.example` y `.env` (tipo «Archivo
  ENV»). El README no explica cómo hacer la copia en Windows ni el riesgo de que quede como
  `.env.txt`.
- `DB_PASSWORD` quedó claro.
- `OLLAMA_MODEL=llama3.2:3b`: se cambió por iniciativa propia, porque el bloque del README
  trae `llama3:8b` sin recordatorio para equipos con menos recursos. **Hace falta ese
  recordatorio.**
- `DB_HOST`, `DB_USER`, `DB_NAME` y `OLLAMA_HOST` se dejaron como vienen.

## 6. Contraseña del Administrador inicial

**Resultado:** OK (no hacía falta por haber cargado `datos_actuales.sql`; se ejecutó solo
para comprobar que el script arranca).

- `.venv\Scripts\python.exe reset_admin.py` mostró
  «Se restablecerá la contraseña de Administrador de prueba (usuario: AdminRH)» y, al
  responder **n**, «Cancelado; no se hizo ningún cambio.».
- La aclaración «Si se cargó `datos_actuales.sql`, este paso no hace falta» está al final
  del paso, después del comando: **llega tarde**. Debe ir antes del comando para que nadie
  lo ejecute sin necesidad.

## 7. Ejecución

**Resultado:** OK. Tiempo aproximado: 2 a 3 minutos hasta ver la pantalla de inicio de
sesión.

- `.venv\Scripts\python.exe -m streamlit run app.py` funcionó tanto en CMD como en
  PowerShell.
- Streamlit no pidió correo en la terminal y Windows no mostró avisos del Firewall.
- El navegador predeterminado (Edge) se abrió solo en `http://localhost:8501` con la
  pantalla de inicio de sesión, sin códigos de error.
- «Con MySQL y Ollama en marcha» se entiende, pero es ambiguo para alguien con pocos
  conocimientos técnicos: conviene decir cómo comprobarlo (servicio `MySQL80` en
  ejecución; ícono de Ollama junto al reloj).

## 8. Revisión en el sistema

**Resultado:** OK. La revisión se hizo en tres bloques.

### Bloque 1: AdminRH (entrada, talentos e IA)

**Resultado:** OK.

| Revisión | Resultado |
|---|---|
| Inicio de sesión con `AdminRH` / `Admin123` | Pidió cambiar la contraseña; las reglas se entienden en pantalla. Se entró con la nueva y, tras cerrar sesión, se volvió a entrar con ella. |
| Inicio | Muestra los accesos a las secciones y el aviso de notificaciones pendientes. |
| Talentos | Aparecen los 60 talentos de prueba; se abrió Adriana Sánchez Castro y se ven sus datos. |
| Evaluación con IA (llama3.2:3b, sin tarjeta de video) | Evaluación completa en unos **60 segundos**, sin códigos de error (dentro del tiempo máximo de 90 s). |
| Historial | Al buscar a la talento en Historial, su línea de tiempo muestra la nueva evaluación. |

### Bloque 2: AdminRH (resto de las secciones)

**Resultado:** OK, con una observación sobre el README.

| Revisión | Resultado |
|---|---|
| Paneles analíticos | Se ven las tarjetas, las gráficas y la matriz 9-box; el clic abre la lista de talentos; filtrar y «Limpiar filtros» funciona. Carga sin demora. |
| Reporte individual | PDF y Excel se descargan y se abren bien; el PDF trae la evaluación nueva (ya elegida en «Evaluación del PDF»). |
| Reporte general | PDF y Excel se descargan y se abren bien. |
| Notificaciones | La bandeja muestra las notificaciones de prueba. |
| Alertas | Se ve la tabla con las 2 alertas de prueba. **No aparece el botón «Crear las alertas sugeridas»**: solo se muestra cuando no hay ninguna alerta, y `datos_actuales.sql` ya trae 2. No es un error del sistema, pero el README («Alertas y notificaciones») lo presenta sin aclarar esa condición. |
| Manuales | Se ven con sus imágenes. |
| Bitácora | Abre sin errores; se ven los inicios de sesión y la evaluación del día. |
| Parámetros del sistema | Abre sin errores y muestra los valores. |
| Configuración | El tema cambia a oscuro y a claro sin cerrar la sesión. |
| Gestión de usuarios | Se ven AdminRH y PruebaE. |

### Bloque 3: PruebaE (Encargado de Finanzas) y sin Ollama

**Resultado:** OK.

| Revisión | Resultado |
|---|---|
| Inicio de sesión con `PruebaE` / `Prueba123` | Pidió cambiar la contraseña y se entró con la nueva. |
| Menú | Talentos, Paneles, Reportes, Historial, Notificaciones, Configuración, Manuales y Soporte. No aparecen Gestión de usuarios, Parámetros del sistema ni Bitácora. |
| Talentos | Solo talentos de Finanzas, con el filtro de área fijo. La ficha es de solo consulta. «Solicitar reevaluación con IA» está como botón al final de «Datos del talento» (no en la pestaña «Evaluación con IA»). |
| Paneles e Historial | Solo muestran datos de Finanzas. |
| Manuales | Solo los del Encargado. |
| Notificaciones | Puede escribir al Administrador de prueba. |
| Sin Ollama (cerrado desde el ícono junto al reloj), con AdminRH | La evaluación con IA muestra **E-101**; Talentos, Paneles y Reportes siguen funcionando. |

## 9. Pruebas automáticas

**Resultado:** OK. `.venv\Scripts\python.exe -m pytest` →
`232 passed, 1 skipped in 72.58s (0:01:12)`, el mismo resultado que en el equipo de
desarrollo.

## Resumen

- **Estado:** prueba terminada. El sistema se instaló y funcionó completo siguiendo el
  README; los problemas encontrados son de instrucciones que faltan o confunden, no del
  sistema.
- **Tiempo de la instalación (pasos 1 a 7):** aproximadamente 1 hora 15 minutos
  (Python 5 min, MySQL 15 min, Ollama 20 min, modelo 8 min, paquetes de Python 10 min,
  base de datos 1 min, arranque del sistema 2 a 3 min), sin contar la lectura del README.
- **Correcciones al README** (por aplicar):
  1. Explicar cómo obtener el código (Git o ZIP) y que la carpeta del proyecto es la que
     contiene `app.py`.
  2. Python: enlace directo a la versión 3.14, marcar **"Add python.exe to PATH"** y usar
     `py -3.14 -m venv .venv`; comprobar con `.venv\Scripts\python.exe --version`.
  3. MySQL: qué instalador descargar, «No thanks, just start my download», tipo
     **Server only** y cómo agregar la carpeta `bin` al PATH.
  4. Ollama: recordatorio de `llama3.2:3b` en el paso de instalación y en el `.env` para
     equipos sin tarjeta de video o con menos de 16 GB.
  5. Cómo abrir una terminal en la carpeta del proyecto; no pegar juntos los comandos del
     entorno de Python.
  6. Los comandos `mysql ... < archivo.sql` son para **CMD** (en PowerShell falla el `<`).
  7. `@contrasena_app` es una contraseña nueva, distinta de la de root, y es la del `.env`.
  8. Cómo copiar `.env.example` como `.env` en Windows sin que quede `.env.txt`.
  9. En el paso 5, avisar **antes** del comando que no hace falta si se cargó
     `datos_actuales.sql`.
  10. Explicar cómo comprobar que MySQL y Ollama están en marcha.
  11. «Alertas y notificaciones»: aclarar que el botón «Crear las alertas sugeridas» solo
      aparece cuando no hay alertas (con `datos_actuales.sql` ya hay 2).
