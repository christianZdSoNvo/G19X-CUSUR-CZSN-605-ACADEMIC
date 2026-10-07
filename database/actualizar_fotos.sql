-- =====================================================================
-- TalentOS: actualización de una base de datos ya instalada
-- Agrega la foto de perfil de talentos y usuarios (PRD, 9.1 y 9.3)
-- =====================================================================
--
-- CUÁNDO SE EJECUTA
--   Solo en una base creada con una versión anterior de crear_bd.sql (sin la
--   columna "foto"). Una instalación nueva con crear_bd.sql ya la incluye.
--
-- CÓMO SE EJECUTA
--   - Con una cuenta de MySQL con privilegios de administración (root), porque el
--     usuario de la aplicación (app_talentos) no tiene permiso de ALTER.
--   - En MySQL Workbench: abrir el archivo y ejecutar todo (rayo).
--
-- No cambia ningún dato existente: la columna nueva queda en NULL y el sistema
-- muestra el avatar genérico hasta que se cargue una foto.
-- =====================================================================

USE proyecto_talentos;

ALTER TABLE Usuarios ADD COLUMN foto MEDIUMBLOB DEFAULT NULL;   -- foto de perfil (JPG 400 x 400)
ALTER TABLE Talentos ADD COLUMN foto MEDIUMBLOB DEFAULT NULL;   -- foto de perfil (JPG 400 x 400)

-- Comprobación: ambas tablas deben mostrar la columna "foto"
SHOW COLUMNS FROM Usuarios LIKE 'foto';
SHOW COLUMNS FROM Talentos LIKE 'foto';
