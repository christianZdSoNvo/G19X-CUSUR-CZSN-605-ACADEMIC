-- =====================================================================
-- TalentOS: actualización de una base de datos ya instalada
-- Manuales por cargo: Administrador de RH y Encargado de área (PRD, 9.4 y 13.4)
-- =====================================================================
--
-- CUÁNDO SE EJECUTA
--   Solo en una base creada con una versión anterior de crear_bd.sql (Manuales sin
--   la columna dirigido_a). Una instalación nueva con crear_bd.sql ya incluye la
--   columna y los manuales iniciales de ambos cargos.
--   Requiere que ya se haya ejecutado actualizar_manuales.sql (tabla Manual_imagenes).
--
-- CÓMO SE EJECUTA
--   - Con una cuenta de MySQL con privilegios de administración (root), porque el
--     usuario de la aplicación (app_talentos) no tiene permiso de ALTER.
--   - En MySQL Workbench: abrir el archivo y ejecutar todo (rayo). Ejecutarlo una sola
--     vez: una segunda ejecución falla en el paso 1 (la columna ya existe).
--
-- QUÉ HACE
--   1. Agrega Manuales.dirigido_a; los manuales que ya existen quedan para el
--      Administrador de RH.
--   2. Copia para el Encargado de área los de las secciones de su menú (todas menos
--      Gestión de usuarios, Parámetros del sistema y Bitácora), con sus imágenes, para
--      que no se quede sin manuales. Después cada copia se edita por separado.
--   3. Registra cada copia en la bitácora.
-- =====================================================================

USE proyecto_talentos;

-- 1. Columna nueva; los manuales actuales quedan para el Administrador de RH
ALTER TABLE Manuales
    ADD COLUMN dirigido_a ENUM('Administrador RH','Encargado de area') NOT NULL
        DEFAULT 'Administrador RH' AFTER id_manual,
    ADD COLUMN id_origen INT NULL,            -- temporal: manual del que sale cada copia
    DROP INDEX ix_manuales_seccion,
    ADD INDEX ix_manuales_cargo_seccion (dirigido_a, seccion_software);

-- 2. Copias para el Encargado de área (texto, enlace e imágenes)
INSERT INTO Manuales (dirigido_a, seccion_software, contenido_texto, fecha_actualizacion,
                      id_usuario_edito, contenido_enlace, id_origen)
SELECT 'Encargado de area', seccion_software, contenido_texto, fecha_actualizacion,
       id_usuario_edito, contenido_enlace, id_manual
FROM Manuales
WHERE dirigido_a = 'Administrador RH'
  AND seccion_software NOT IN ('Gestión de usuarios', 'Parámetros del sistema', 'Bitácora')
ORDER BY id_manual;

INSERT INTO Manual_imagenes (id_manual, orden, imagen)
SELECT copia.id_manual, imagen.orden, imagen.imagen
FROM Manuales copia
JOIN Manual_imagenes imagen ON imagen.id_manual = copia.id_origen
ORDER BY copia.id_manual, imagen.orden, imagen.id_imagen;

-- 3. Bitácora de las copias
INSERT INTO Bitacora (id_usuario, accion, tabla_afectada, id_registro_afectado, detalle)
SELECT NULL, 'alta', 'Manuales', id_manual,
       JSON_OBJECT('origen', 'actualizar_manuales_por_cargo.sql', 'dirigido_a', dirigido_a,
                   'seccion_software', seccion_software, 'copia_de', id_origen)
FROM Manuales
WHERE id_origen IS NOT NULL;

-- 4. Se quitan la columna temporal y el valor por omisión (el sistema siempre indica el cargo)
ALTER TABLE Manuales
    DROP COLUMN id_origen,
    ALTER COLUMN dirigido_a DROP DEFAULT;

-- Comprobación: cada manual con su cargo y su número de imágenes
SELECT m.id_manual, m.dirigido_a, m.seccion_software,
       (SELECT COUNT(*) FROM Manual_imagenes i WHERE i.id_manual = m.id_manual) AS imagenes
FROM Manuales m
ORDER BY m.dirigido_a, m.id_manual;
