-- =====================================================================
-- TalentOS (Talent Overview System): Sistema de Identificación de Talento de Alto Potencial
-- Script de instalación de la base de datos (PRD, sección 9)
-- MySQL 8.0.17 o superior
-- =====================================================================
--
-- QUÉ HACE ESTE SCRIPT
--   1. Crea la base de datos proyecto_talentos.
--   2. Crea las 10 tablas del modelo de datos.
--   3. Crea el usuario de MySQL de la aplicación con privilegios mínimos.
--   4. Carga las claves iniciales de Configuracion_sistema.
--   5. Crea el Administrador de RH inicial (sin contraseña: se le asigna
--      después con reset_admin.py).
--   6. Carga los manuales iniciales.
--   7. (Opcional) Cifrado de tablespaces y SSL obligatorio.
--
-- CÓMO SE EJECUTA
--   - Con una cuenta de MySQL con privilegios de administración (root).
--   - En MySQL Workbench: abrir el archivo y ejecutar todo (rayo).
--   - En consola:  mysql -u root -p < database\crear_bd.sql
--
-- ANTES DE EJECUTARLO
--   Llenar los valores de la sección "0. Valores de la instalación".
--   Esos valores (contraseñas incluidas) NO se guardan en este archivo:
--   se escriben solo al ejecutarlo y se deshacen antes de un commit.
--
-- CONTRASEÑAS DE LOS USUARIOS DEL SISTEMA
--   contrasena = "pbkdf2_sha256$<iteraciones>$<hash base64>" (PBKDF2-SHA256)
--   salt       = 16 caracteres hexadecimales aleatorios
--   Las calcula el sistema en Python (backend/seguridad.py); MySQL no tiene
--   PBKDF2, por eso este script no guarda ninguna contraseña de usuario.
--
-- DESPUÉS DE EJECUTARLO
--   En la carpeta del proyecto:  .venv\Scripts\python.exe reset_admin.py
--   Asigna la contraseña temporal del Administrador inicial; se cambia en el
--   primer inicio de sesión.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 0. Valores de la instalación
-- ---------------------------------------------------------------------
-- Contraseña del usuario de MySQL que usará la aplicación (va al .env).
SET @contrasena_app = 'CAMBIAR_contrasena_app';

-- Datos del Administrador de RH inicial.
-- Su contraseña no va aquí: se asigna con reset_admin.py al terminar.
SET @admin_nombre  = 'CAMBIAR nombre del administrador';
SET @admin_usuario = 'admin';
SET @admin_correo  = 'CAMBIAR@correo.com';
SET @admin_tel     = '0000000000';


-- ---------------------------------------------------------------------
-- 1. Base de datos
-- ---------------------------------------------------------------------
-- Si ya existe, este comando falla a propósito para no borrar datos.
-- Solo en desarrollo, para reinstalar desde cero, descomentar:
-- DROP DATABASE IF EXISTS proyecto_talentos;

CREATE DATABASE proyecto_talentos
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;

USE proyecto_talentos;


-- ---------------------------------------------------------------------
-- 2. Tablas
-- ---------------------------------------------------------------------
-- Orden de creación según las llaves foráneas:
-- Usuarios -> Talentos -> Evaluaciones -> Eventos_talento -> Manuales -> Manual_imagenes
-- -> Notificaciones -> Bitacora -> Alertas_config -> Configuracion_sistema

-- 9.3 Usuarios
CREATE TABLE Usuarios (
    id_usuario              INT AUTO_INCREMENT PRIMARY KEY,
    cargo                   ENUM('Administrador RH','Encargado de area') NOT NULL,
    area                    VARCHAR(100) NOT NULL,
    nombre                  VARCHAR(50)  NOT NULL,
    usuario                 VARCHAR(30)  NOT NULL,
    correo                  VARCHAR(70)  NOT NULL,
    contrasena              VARCHAR(70)  NOT NULL,
    salt                    CHAR(16)     NOT NULL,
    activo                  BOOLEAN      DEFAULT TRUE,
    intentos_fallidos       TINYINT      DEFAULT 0,
    bloqueado_hasta         DATETIME     DEFAULT NULL,
    fecha_cambio_contrasena DATE         NOT NULL,
    debe_cambiar_contrasena BOOLEAN      DEFAULT TRUE,
    tel_mx                  VARCHAR(10)  NOT NULL,
    foto                    MEDIUMBLOB   DEFAULT NULL,   -- foto de perfil (JPG 400 x 400)
    CONSTRAINT uq_usuarios_usuario UNIQUE (usuario),
    CONSTRAINT uq_usuarios_correo  UNIQUE (correo),
    CONSTRAINT ck_usuarios_tel     CHECK (tel_mx REGEXP '^[0-9]{10}$')
) ENGINE = InnoDB;

-- 9.1 Talentos
CREATE TABLE Talentos (
    id_talento         INT AUTO_INCREMENT PRIMARY KEY,
    area               VARCHAR(100) NOT NULL,
    nombre             VARCHAR(50)  NOT NULL,
    correo             VARCHAR(70)  NOT NULL,
    tel_mx             VARCHAR(10)  NOT NULL,
    fecha_ingreso      DATE         NOT NULL,
    desempeno_previo   TINYINT      DEFAULT NULL,
    competencias       VARCHAR(200) DEFAULT 'Sin registro',
    capacitacion       VARCHAR(400) DEFAULT 'Sin registro',
    experiencia        VARCHAR(300) DEFAULT 'Sin registro',
    objetivos_futuros  VARCHAR(200) DEFAULT 'Sin registro',
    liderazgo_previo   VARCHAR(300) DEFAULT 'Sin registro',
    activo             BOOLEAN      DEFAULT TRUE,
    fecha_baja         DATE         DEFAULT NULL,
    motivo_baja        VARCHAR(200) DEFAULT NULL,
    fecha_modificacion DATE         NOT NULL,
    foto               MEDIUMBLOB   DEFAULT NULL,   -- foto de perfil (JPG 400 x 400)
    CONSTRAINT uq_talentos_correo    UNIQUE (correo),
    CONSTRAINT ck_talentos_tel       CHECK (tel_mx REGEXP '^[0-9]{10}$'),
    CONSTRAINT ck_talentos_desempeno CHECK (desempeno_previo BETWEEN 0 AND 100),
    INDEX ix_talentos_area_activo (area, activo),
    INDEX ix_talentos_nombre (nombre)
) ENGINE = InnoDB;

-- 9.2 Evaluaciones
-- Las columnas de TEXT solo aceptan un DEFAULT escrito entre paréntesis.
-- ON DELETE CASCADE: el borrado físico de un talento (ARCO o retención)
-- borra también sus evaluaciones.
CREATE TABLE Evaluaciones (
    id_evaluacion               INT AUTO_INCREMENT PRIMARY KEY,
    id_talento                  INT NOT NULL,
    reporte_ia                  TEXT        DEFAULT ('Sin reporte'),
    puntuacion_talento_por_ia   TINYINT     DEFAULT NULL,
    fecha_evaluacion            DATE        DEFAULT NULL,
    clasificacion_9box          VARCHAR(30) DEFAULT NULL,
    potencial_crecimiento_nivel ENUM('bajo','medio','alto') NOT NULL,
    desempeno_pre_ev            ENUM('bajo','medio','alto') NOT NULL,
    resultados_cap_ev           ENUM('bajo','medio','alto') NOT NULL,
    experiencia_lab_ev          ENUM('bajo','medio','alto') NOT NULL,
    objetivos_fut_ev            ENUM('bajo','medio','alto') NOT NULL,
    competencias_ev             ENUM('bajo','medio','alto') NOT NULL,
    liderazgo_prev_ev           ENUM('bajo','medio','alto') NOT NULL,
    CONSTRAINT fk_evaluaciones_talento FOREIGN KEY (id_talento)
        REFERENCES Talentos (id_talento) ON DELETE CASCADE,
    CONSTRAINT ck_evaluaciones_puntuacion
        CHECK (puntuacion_talento_por_ia BETWEEN 0 AND 100),
    -- Coherencia puntuación-nivel (PRD, sección 10)
    CONSTRAINT ck_evaluaciones_coherencia CHECK (
        puntuacion_talento_por_ia IS NULL
        OR (potencial_crecimiento_nivel = 'bajo'  AND puntuacion_talento_por_ia BETWEEN 0  AND 30)
        OR (potencial_crecimiento_nivel = 'medio' AND puntuacion_talento_por_ia BETWEEN 31 AND 70)
        OR (potencial_crecimiento_nivel = 'alto'  AND puntuacion_talento_por_ia BETWEEN 71 AND 100)
    ),
    INDEX ix_evaluaciones_talento_fecha (id_talento, fecha_evaluacion)
) ENGINE = InnoDB;

-- 9.6 Eventos_talento
CREATE TABLE Eventos_talento (
    id_evento           INT AUTO_INCREMENT PRIMARY KEY,
    id_talento          INT NOT NULL,
    tipo_evento         ENUM('ingreso','promocion','capacitacion','cambio_area',
                             'cambio_desempeno','evaluacion_ia',
                             'cambio_clasificacion','otro') NOT NULL,
    descripcion         VARCHAR(300) NOT NULL,
    fecha_evento        DATE         NOT NULL,
    id_usuario_registro INT          NOT NULL,
    fecha_registro      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_eventos_talento FOREIGN KEY (id_talento)
        REFERENCES Talentos (id_talento) ON DELETE CASCADE,
    CONSTRAINT fk_eventos_usuario FOREIGN KEY (id_usuario_registro)
        REFERENCES Usuarios (id_usuario),
    INDEX ix_eventos_talento_fecha (id_talento, fecha_evento)
) ENGINE = InnoDB;

-- 9.4 Manuales
-- dirigido_a: cargo que consulta el manual (mismos valores que Usuarios.cargo);
-- el Administrador y el Encargado tienen manuales distintos.
CREATE TABLE Manuales (
    id_manual           INT AUTO_INCREMENT PRIMARY KEY,
    dirigido_a          ENUM('Administrador RH','Encargado de area') NOT NULL,
    seccion_software    VARCHAR(40),
    contenido_texto     LONGTEXT,
    fecha_actualizacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_usuario_edito    INT      NOT NULL,
    contenido_enlace    VARCHAR(255),
    CONSTRAINT fk_manuales_usuario FOREIGN KEY (id_usuario_edito)
        REFERENCES Usuarios (id_usuario),
    INDEX ix_manuales_cargo_seccion (dirigido_a, seccion_software)
) ENGINE = InnoDB;

-- 9.4.1 Imágenes de los manuales (varias por manual, en orden)
CREATE TABLE Manual_imagenes (
    id_imagen INT AUTO_INCREMENT PRIMARY KEY,
    id_manual INT        NOT NULL,
    orden     SMALLINT   NOT NULL,          -- 1, 2, 3... en el orden en que se muestran
    imagen    MEDIUMBLOB NOT NULL,          -- PNG o JPG de hasta 5 MB
    CONSTRAINT fk_manual_imagenes_manual FOREIGN KEY (id_manual)
        REFERENCES Manuales (id_manual) ON DELETE CASCADE,
    INDEX ix_manual_imagenes_orden (id_manual, orden)
) ENGINE = InnoDB;

-- 9.5 Notificaciones
-- ON DELETE SET NULL: si se borra físicamente el talento relacionado,
-- la notificación se conserva sin el vínculo.
CREATE TABLE Notificaciones (
    id_noti          INT AUTO_INCREMENT PRIMARY KEY,
    fecha_creacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_emisor        INT      DEFAULT NULL,
    id_destinatario  INT      NOT NULL,
    contenido        TEXT     DEFAULT ('Notificación emitida'),
    estado           ENUM('pendiente','revisado') DEFAULT 'pendiente',
    tipo             ENUM('correccion_datos','reevaluacion','alerta_automatica',
                          'restablecer_acceso','error_sistema','otro') DEFAULT 'otro',
    id_talento       INT      DEFAULT NULL,
    respuesta        TEXT     DEFAULT NULL,
    fecha_revision   DATETIME DEFAULT NULL,
    grado_emergencia ENUM('bajo','medio','alto') DEFAULT 'bajo',
    CONSTRAINT fk_notificaciones_emisor FOREIGN KEY (id_emisor)
        REFERENCES Usuarios (id_usuario),
    CONSTRAINT fk_notificaciones_destinatario FOREIGN KEY (id_destinatario)
        REFERENCES Usuarios (id_usuario),
    CONSTRAINT fk_notificaciones_talento FOREIGN KEY (id_talento)
        REFERENCES Talentos (id_talento) ON DELETE SET NULL,
    INDEX ix_notificaciones_bandeja (id_destinatario, estado)
) ENGINE = InnoDB;

-- 9.7 Bitacora
CREATE TABLE Bitacora (
    id_bitacora          INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario           INT      DEFAULT NULL,
    fecha_hora           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accion               ENUM('inicio_sesion','cierre_sesion','intento_fallido',
                              'alta','edicion','baja','eliminacion',
                              'evaluacion_ia','exportacion','configuracion') NOT NULL,
    tabla_afectada       VARCHAR(50) DEFAULT NULL,
    id_registro_afectado INT         DEFAULT NULL,
    detalle              TEXT        DEFAULT NULL,
    CONSTRAINT fk_bitacora_usuario FOREIGN KEY (id_usuario)
        REFERENCES Usuarios (id_usuario),
    INDEX ix_bitacora_fecha (fecha_hora),
    INDEX ix_bitacora_usuario_accion (id_usuario, accion)
) ENGINE = InnoDB;

-- 9.8 Alertas_config
CREATE TABLE Alertas_config (
    id_alerta          INT AUTO_INCREMENT PRIMARY KEY,
    id_usuario_creador INT         NOT NULL,
    nombre             VARCHAR(80) NOT NULL,
    indicador          ENUM('puntuacion_ia','nivel_potencial',
                            'desempeno_previo','sin_evaluacion') NOT NULL,
    condicion          ENUM('disminuye','aumenta','cambia','dias_sin_evaluar') NOT NULL,
    umbral             INT          DEFAULT 10,
    area               VARCHAR(100) DEFAULT NULL,
    id_destinatario    INT          NOT NULL,
    grado_emergencia   ENUM('bajo','medio','alto') DEFAULT 'medio',
    activa             BOOLEAN      DEFAULT TRUE,
    fecha_creacion     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_alertas_creador FOREIGN KEY (id_usuario_creador)
        REFERENCES Usuarios (id_usuario),
    CONSTRAINT fk_alertas_destinatario FOREIGN KEY (id_destinatario)
        REFERENCES Usuarios (id_usuario)
) ENGINE = InnoDB;

-- 9.9 Configuracion_sistema
CREATE TABLE Configuracion_sistema (
    id_config           INT AUTO_INCREMENT PRIMARY KEY,
    clave               VARCHAR(50)  NOT NULL,
    valor               VARCHAR(255) NOT NULL,
    descripcion         VARCHAR(200) DEFAULT NULL,
    id_usuario_modifico INT          DEFAULT NULL,
    fecha_modificacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_configuracion_clave UNIQUE (clave),
    CONSTRAINT fk_configuracion_usuario FOREIGN KEY (id_usuario_modifico)
        REFERENCES Usuarios (id_usuario)
) ENGINE = InnoDB;


-- ---------------------------------------------------------------------
-- 3. Usuario de MySQL de la aplicación (PRD, 12.2)
-- ---------------------------------------------------------------------
-- Solo SELECT, INSERT, UPDATE y DELETE; sin DROP ni ALTER.
-- Bitacora solo recibe SELECT e INSERT para que la aplicación no pueda
-- editarla ni borrarla (PRD, 8.5).
-- REQUIRE SSL obliga a que la conexión de este usuario vaya cifrada.
-- CREATE USER no acepta variables; se arma como sentencia preparada.

SET @sql = CONCAT(
    'CREATE USER ''app_talentos''@''localhost'' IDENTIFIED BY ',
    QUOTE(@contrasena_app),
    ' REQUIRE SSL'
);
PREPARE crear_usuario FROM @sql;
EXECUTE crear_usuario;
DEALLOCATE PREPARE crear_usuario;
SET @sql = NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Usuarios              TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Talentos              TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Evaluaciones          TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Eventos_talento       TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Manuales              TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Manual_imagenes       TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Notificaciones        TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT                 ON proyecto_talentos.Bitacora              TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Alertas_config        TO 'app_talentos'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Configuracion_sistema TO 'app_talentos'@'localhost';


-- ---------------------------------------------------------------------
-- 4. Administrador de RH inicial
-- ---------------------------------------------------------------------
-- Se crea con contrasena = 'pendiente', que no coincide con ninguna
-- contraseña: nadie puede entrar con esta cuenta hasta ejecutar
-- reset_admin.py. Sus datos y su ID ya sirven para los manuales iniciales.
SET @salt = LOWER(HEX(RANDOM_BYTES(8)));

INSERT INTO Usuarios (cargo, area, nombre, usuario, correo, contrasena, salt,
                      fecha_cambio_contrasena, debe_cambiar_contrasena, tel_mx)
VALUES ('Administrador RH', 'Recursos Humanos', @admin_nombre, @admin_usuario,
        @admin_correo, 'pendiente', @salt, CURDATE(), TRUE, @admin_tel);

SET @id_admin = LAST_INSERT_ID();
SET @salt = NULL;
SET @contrasena_app = NULL;

INSERT INTO Bitacora (id_usuario, accion, tabla_afectada, id_registro_afectado, detalle)
VALUES (@id_admin, 'alta', 'Usuarios', @id_admin,
        '{"origen": "script de instalación", "cargo": "Administrador RH"}');


-- ---------------------------------------------------------------------
-- 5. Claves iniciales de Configuracion_sistema (PRD, 9.9)
-- ---------------------------------------------------------------------
-- Los datos de soporte quedan "Por definir" hasta que se decidan
-- (decisión pendiente 3); se editan en Configuración > Parámetros.
INSERT INTO Configuracion_sistema (clave, valor, descripcion) VALUES
    ('correo_soporte',             'Por definir', 'Correo del contacto de soporte'),
    ('telefono_soporte',           'Por definir', 'Teléfono del contacto de soporte'),
    ('nombre_soporte',             'Por definir', 'Nombre del contacto de soporte'),
    ('tiempo_max_ia_seg',          '90',          'Tiempo máximo de espera de la respuesta de la IA, en segundos'),
    ('intentos_ia_por_dia',        '3',           'Evaluaciones con IA por talento en un día'),
    ('variacion_alerta_default',   '10',          'Variación en puntos que dispara una alerta por defecto'),
    ('max_intentos_login',         '5',           'Intentos fallidos antes de bloquear la cuenta'),
    ('minutos_bloqueo',            '15',          'Minutos que dura el bloqueo de la cuenta'),
    ('minutos_inactividad_sesion', '30',          'Minutos de inactividad antes de cerrar la sesión');


-- ---------------------------------------------------------------------
-- 6. Manuales iniciales (PRD, 9.4)
-- ---------------------------------------------------------------------
-- 6.1 Manuales del Administrador de RH (todas las secciones)
INSERT INTO Manuales (dirigido_a, seccion_software, contenido_texto, id_usuario_edito) VALUES
    ('Administrador RH', 'Inicio de sesión',
     'Escriba su usuario y contraseña y pulse "Iniciar sesión". En el primer inicio de sesión, o después de un restablecimiento, el sistema pide una contraseña nueva de al menos 8 caracteres con una mayúscula, una minúscula y un número. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos. Si olvidó su usuario o contraseña, pulse "¿Olvidaste tu usuario o contraseña?", escriba su correo y el Administrador de RH se pondrá en contacto con usted.',
     @id_admin),
    ('Administrador RH', 'Talentos',
     'Busque a un talento por ID o por nombre, o filtre la lista por área. Al seleccionarlo verá sus datos y la pestaña "Evaluación con IA". El Administrador de RH da de alta talentos en "Nuevo talento", los edita, los da de baja con un motivo y los evalúa con el botón "Evaluar" (hay un número limitado de evaluaciones por talento al día). El Encargado de área consulta los talentos de su área y puede solicitar una corrección de datos o una reevaluación con IA.',
     @id_admin),
    ('Administrador RH', 'Paneles analíticos',
     'Muestra los indicadores generales, la distribución por nivel de potencial, la matriz 9-box, el promedio de puntuación por área, el histograma de puntuaciones y la evolución mensual. Use los filtros de la parte superior para acotar los datos. Haga clic en un área o en una celda de la matriz 9-box para ver el detalle hasta llegar al perfil del talento.',
     @id_admin),
    ('Administrador RH', 'Reportes',
     'Busque a un talento por ID o por nombre, o selecciónelo en la lista general. Desde su perfil puede exportar el reporte individual en PDF o Excel. El reporte general se genera con los filtros aplicados. Si el archivo no se puede generar, el sistema entrega un archivo de texto con los mismos datos.',
     @id_admin),
    ('Administrador RH', 'Historial y evolución',
     'Seleccione a un talento para ver su línea de tiempo: la puntuación de la IA de cada evaluación en el eje vertical y la fecha en el horizontal, junto con sus eventos (promociones, capacitaciones, cambios de clasificación, etc.).',
     @id_admin),
    ('Administrador RH', 'Notificaciones',
     'En "Bandeja" consulte sus notificaciones y su estado. En "Nueva notificación" elija el tipo, el talento (opcional), el grado de emergencia y escriba el texto. En "Alertas" configure reglas que generan notificaciones automáticas cuando cambian los indicadores de los talentos.',
     @id_admin),
    ('Administrador RH', 'Configuración',
     'Cambie su contraseña, el tema claro u oscuro, consulte el contacto de soporte o cierre sesión. El Administrador de RH además gestiona usuarios, parámetros del sistema, manuales y consulta la bitácora.',
     @id_admin),
    ('Administrador RH', 'Gestión de usuarios',
     'Dé de alta usuarios con su cargo y área; el sistema genera una contraseña temporal que se muestra una sola vez y debe comunicarse en persona. Desde la lista puede editar, desactivar o reactivar usuarios y restablecer su contraseña (también desbloquea la cuenta). En "Solicitudes" aparecen los pedidos de restablecimiento hechos desde el inicio de sesión.',
     @id_admin),
    ('Administrador RH', 'Parámetros del sistema',
     'Modifique el contacto de soporte, el tiempo máximo y el número de evaluaciones diarias de la IA, la variación por defecto de las alertas, los intentos antes del bloqueo, los minutos de bloqueo y los minutos de inactividad. Pulse "Guardar": los cambios se aplican de inmediato y quedan en la bitácora.',
     @id_admin),
    ('Administrador RH', 'Bitácora',
     'Consulte las acciones registradas en el sistema (inicios de sesión, altas, ediciones, bajas, evaluaciones, exportaciones y cambios de configuración). Filtre por fechas, usuario, acción y tabla. La bitácora no se puede editar ni borrar.',
     @id_admin),
    ('Administrador RH', 'Soporte',
     'En la pestaña "Manuales" elija la sección del sistema o busque por texto. En "Contacto" encontrará los datos de soporte y el botón "Escribir correo"; si apareció un código de error, inclúyalo en el mensaje.',
     @id_admin);

-- 6.2 Manuales del Encargado de área (solo las secciones de su menú)
INSERT INTO Manuales (dirigido_a, seccion_software, contenido_texto, id_usuario_edito) VALUES
    ('Encargado de area', 'Inicio de sesión',
     'Escriba su usuario y contraseña y pulse "Iniciar sesión". En el primer inicio de sesión, o después de un restablecimiento, el sistema pide una contraseña nueva de al menos 8 caracteres con una mayúscula, una minúscula y un número. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos. Si olvidó su usuario o contraseña, pulse "¿Olvidaste tu usuario o contraseña?", escriba su correo y el Administrador de RH se pondrá en contacto con usted.',
     @id_admin),
    ('Encargado de area', 'Talentos',
     'Consulte los talentos de su área: búsquelos por ID o por nombre. Al seleccionar uno verá sus datos y su última evaluación con IA. Si un dato es incorrecto, pulse "Solicitar corrección de datos"; si necesita una evaluación más reciente, pulse "Solicitar reevaluación con IA". Ambas solicitudes llegan al Administrador de RH como notificación.',
     @id_admin),
    ('Encargado de area', 'Paneles analíticos',
     'Muestra los indicadores de los talentos de su área: distribución por nivel de potencial, matriz 9-box, histograma de puntuaciones y evolución mensual. En la barra lateral elija qué paneles mostrar. Haga clic en un nivel o en una celda de la matriz 9-box para ver el detalle hasta llegar al perfil del talento.',
     @id_admin),
    ('Encargado de area', 'Reportes',
     'Busque a un talento de su área por ID o por nombre, o selecciónelo en la lista. Puede exportar su reporte individual en PDF o Excel, o el reporte general de su área con los filtros aplicados. Si el archivo no se puede generar, el sistema entrega un archivo de texto con los mismos datos.',
     @id_admin),
    ('Encargado de area', 'Historial y evolución',
     'Seleccione a un talento de su área para ver su línea de tiempo: la puntuación de la IA de cada evaluación en el eje vertical y la fecha en el horizontal, junto con sus eventos (promociones, capacitaciones, cambios de clasificación, etc.).',
     @id_admin),
    ('Encargado de area', 'Notificaciones',
     'En "Bandeja" consulte las notificaciones recibidas y enviadas. En "Nueva notificación" escriba al Administrador de RH: elija el tipo, el talento de su área (opcional), el grado de emergencia y el texto. En "Alertas" configure reglas que le avisan cuando cambian los indicadores de los talentos de su área.',
     @id_admin),
    ('Encargado de area', 'Configuración',
     'Cambie su contraseña y su foto de perfil, elija el tema claro u oscuro, consulte el contacto de soporte o cierre sesión.',
     @id_admin),
    ('Encargado de area', 'Soporte',
     'En la pestaña "Manuales" elija la sección del sistema o busque por texto. En "Contacto" encontrará los datos de soporte y el botón "Escribir correo"; si apareció un código de error, inclúyalo en el mensaje.',
     @id_admin);

SET @id_admin = NULL;


-- ---------------------------------------------------------------------
-- 7. (Opcional) Cifrado en reposo y SSL obligatorio (PRD, 8.1)
-- ---------------------------------------------------------------------
-- Se dejan comentados porque requieren cambios en el servidor.
--
-- 7.1 Cifrado de tablespaces: requiere el plugin keyring en my.ini
--     (sección [mysqld]) y reiniciar el servicio "mysql8":
--         early-plugin-load = keyring_file.dll
--         keyring_file_data = C:/AppServ/MySQL/keyring/keyring
--     Comprobar:  SELECT PLUGIN_NAME, PLUGIN_STATUS FROM INFORMATION_SCHEMA.PLUGINS
--                 WHERE PLUGIN_NAME LIKE 'keyring%';
--     El archivo keyring se debe respaldar: sin él, las tablas no se pueden leer.
--
-- ALTER TABLE Talentos        ENCRYPTION = 'Y';
-- ALTER TABLE Evaluaciones    ENCRYPTION = 'Y';
-- ALTER TABLE Eventos_talento ENCRYPTION = 'Y';
--
-- 7.2 SSL obligatorio para todas las conexiones (no solo app_talentos):
--     Comprobar primero que el servidor tiene SSL:
--         SHOW VARIABLES LIKE 'have_ssl';   -- debe decir YES
--
-- SET PERSIST require_secure_transport = ON;


-- ---------------------------------------------------------------------
-- 8. Verificación
-- ---------------------------------------------------------------------
SHOW TABLES;
SELECT id_usuario, cargo, usuario, debe_cambiar_contrasena FROM Usuarios;
SELECT clave, valor FROM Configuracion_sistema;
SELECT id_manual, dirigido_a, seccion_software FROM Manuales;
SHOW GRANTS FOR 'app_talentos'@'localhost';

-- Después de ejecutar el script, en el .env:
--   DB_USER=app_talentos
--   DB_PASSWORD=<la contraseña de @contrasena_app>
--
-- Y en la carpeta del proyecto, para la contraseña temporal del Administrador:
--   .venv\Scripts\python.exe reset_admin.py
--
-- Para cargar los datos de prueba (usuarios, talentos, evaluaciones,
-- notificaciones, etc.), ejecutar después database\datos_actuales.sql con
-- root. En ese caso el Administrador inicial de la sección 4 se reemplaza por
-- los usuarios del archivo. Los manuales con imágenes están aparte, en
-- database\imagenes_manuales.sql (opcional, después de datos_actuales.sql).
