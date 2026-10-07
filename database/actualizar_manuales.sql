-- =====================================================================
-- TalentOS: actualización de una base de datos ya instalada
-- Varias imágenes por manual (PRD, 9.4 y 9.4.1)
-- =====================================================================
--
-- CUÁNDO SE EJECUTA
--   Solo en una base creada con una versión anterior de crear_bd.sql (con la
--   columna Manuales.contenido_imagen). Una instalación nueva con crear_bd.sql ya
--   incluye la tabla Manual_imagenes.
--
-- CÓMO SE EJECUTA
--   - Con una cuenta de MySQL con privilegios de administración (root), porque el
--     usuario de la aplicación (app_talentos) no tiene permiso de CREATE, ALTER ni GRANT.
--   - En MySQL Workbench: abrir el archivo y ejecutar todo (rayo).
--
-- No se pierde ninguna imagen: la de cada manual pasa a Manual_imagenes como su
-- primera imagen antes de quitar la columna anterior.
-- =====================================================================

USE proyecto_talentos;

-- 1. Tabla nueva: imágenes de cada manual, en orden
CREATE TABLE Manual_imagenes (
    id_imagen INT AUTO_INCREMENT PRIMARY KEY,
    id_manual INT        NOT NULL,
    orden     SMALLINT   NOT NULL,          -- 1, 2, 3... en el orden en que se muestran
    imagen    MEDIUMBLOB NOT NULL,          -- PNG o JPG de hasta 5 MB
    CONSTRAINT fk_manual_imagenes_manual FOREIGN KEY (id_manual)
        REFERENCES Manuales (id_manual) ON DELETE CASCADE,
    INDEX ix_manual_imagenes_orden (id_manual, orden)
) ENGINE = InnoDB;

-- 2. La imagen que ya tenía cada manual pasa a ser su primera imagen
INSERT INTO Manual_imagenes (id_manual, orden, imagen)
SELECT id_manual, 1, contenido_imagen FROM Manuales WHERE contenido_imagen IS NOT NULL;

-- 3. Se quita la columna anterior
ALTER TABLE Manuales DROP COLUMN contenido_imagen;

-- 4. Permisos del usuario de la aplicación
GRANT SELECT, INSERT, UPDATE, DELETE ON proyecto_talentos.Manual_imagenes TO 'app_talentos'@'localhost';

-- Comprobación: Manuales ya no tiene contenido_imagen y la tabla nueva existe
SHOW COLUMNS FROM Manuales;
SELECT id_manual, COUNT(*) AS imagenes FROM Manual_imagenes GROUP BY id_manual;
SHOW GRANTS FOR 'app_talentos'@'localhost';
