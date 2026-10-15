"""Exporta todos los registros de la base de datos a database/datos_actuales.sql.

Uso (en la carpeta del proyecto):
    .venv\\Scripts\\python.exe exportar_datos.py

El script generado se ejecuta con root DESPUÉS de crear_bd.sql: borra los registros
iniciales (Administrador, configuración, manuales y bitácora de la instalación) y carga
los actuales con los mismos IDs. Las contraseñas de los usuarios se conservan (hash y
salt); los intentos fallidos y los bloqueos se reinician.
"""

import datetime
import decimal
from pathlib import Path

from backend import db

ARCHIVO = Path(__file__).parent / "database" / "datos_actuales.sql"

# Orden de las llaves foráneas (el mismo de crear_bd.sql)
TABLAS = ("Usuarios", "Talentos", "Evaluaciones", "Eventos_talento", "Manuales", "Manual_imagenes",
          "Notificaciones", "Bitacora", "Alertas_config", "Configuracion_sistema")
LLAVES = {"Usuarios": "id_usuario", "Talentos": "id_talento", "Evaluaciones": "id_evaluacion",
          "Eventos_talento": "id_evento", "Manuales": "id_manual", "Manual_imagenes": "id_imagen",
          "Notificaciones": "id_noti", "Bitacora": "id_bitacora", "Alertas_config": "id_alerta",
          "Configuracion_sistema": "id_config"}
# Filas por INSERT; las tablas con imágenes van de una en una para no hacer sentencias enormes
FILAS_POR_INSERT = 50
CON_IMAGENES = ("Usuarios", "Talentos", "Manual_imagenes")

ESCAPES = {"\\": "\\\\", "'": "''", "\n": "\\n", "\r": "\\r", "\0": "\\0", "\x1a": "\\Z"}


def literal(valor):
    # Valor de Python -> literal de MySQL
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    if isinstance(valor, (int, decimal.Decimal)):
        return str(valor)
    if isinstance(valor, (bytes, bytearray)):
        return "0x" + valor.hex() if valor else "''"
    if isinstance(valor, (datetime.date, datetime.datetime, datetime.timedelta)):
        return f"'{valor}'"
    return "'" + "".join(ESCAPES.get(c, c) for c in str(valor)) + "'"


def filas(cursor, tabla):
    cursor.execute(f"SELECT * FROM {tabla} ORDER BY {LLAVES[tabla]}")
    columnas = [d[0] for d in cursor.description]
    registros = cursor.fetchall()
    if tabla == "Usuarios":
        for registro in registros:
            registro["intentos_fallidos"] = 0
            registro["bloqueado_hasta"] = None
    return columnas, registros


def inserts(tabla, columnas, registros):
    tamano = 1 if tabla in CON_IMAGENES else FILAS_POR_INSERT
    encabezado = f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES"
    for inicio in range(0, len(registros), tamano):
        grupo = registros[inicio:inicio + tamano]
        valores = ",\n".join("    (" + ", ".join(literal(r[c]) for c in columnas) + ")" for r in grupo)
        yield f"{encabezado}\n{valores};"


def generar():
    partes = [
        "-- =====================================================================",
        "-- TalentOS: registros actuales de la base de datos",
        f"-- Generado con exportar_datos.py el {datetime.datetime.now():%d/%m/%Y %H:%M}",
        "-- =====================================================================",
        "--",
        "-- CÓMO SE EJECUTA",
        "--   1. Ejecutar primero database/crear_bd.sql (crea la base, las tablas y",
        "--      el usuario de MySQL app_talentos).",
        "--   2. Ejecutar este archivo con root:",
        "--        mysql -u root -p < database\\datos_actuales.sql",
        "--      o abrirlo en MySQL Workbench y ejecutar todo (rayo).",
        "--",
        "-- Borra los registros iniciales de crear_bd.sql (Administrador, configuración,",
        "-- manuales y bitácora de la instalación) y carga los actuales con sus mismos",
        "-- IDs. Los usuarios entran con sus contraseñas actuales.",
        "-- =====================================================================",
        "",
        "SET NAMES utf8mb4;",
        "USE proyecto_talentos;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "START TRANSACTION;",
        "",
    ]
    partes += [f"DELETE FROM {tabla};" for tabla in reversed(TABLAS)]
    resumen = []
    with db.transaccion() as cursor:
        for tabla in TABLAS:
            columnas, registros = filas(cursor, tabla)
            resumen.append((tabla, len(registros)))
            partes += ["", f"-- {tabla} ({len(registros)} registros)"]
            partes += list(inserts(tabla, columnas, registros))
    partes += ["", "COMMIT;", "SET FOREIGN_KEY_CHECKS = 1;", "",
               "-- Verificación"]
    partes += [f"SELECT '{tabla}' AS tabla, COUNT(*) AS registros FROM {tabla}"
               + (";" if i == len(TABLAS) - 1 else " UNION ALL") for i, tabla in enumerate(TABLAS)]
    ARCHIVO.write_text("\n".join(partes) + "\n", encoding="utf-8", newline="\n")
    return resumen


def main():
    resumen = generar()
    for tabla, cantidad in resumen:
        print(f"{tabla:<22} {cantidad:>5}")
    print(f"Archivo: {ARCHIVO} ({ARCHIVO.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
