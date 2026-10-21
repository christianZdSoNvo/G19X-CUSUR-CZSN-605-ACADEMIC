"""Exporta los registros de la base de datos a database/datos_actuales.sql, sin datos personales.

Uso (en la carpeta del proyecto):
    .venv\\Scripts\\python.exe exportar_datos.py

El script generado se ejecuta con root DESPUÉS de crear_bd.sql: borra los registros
iniciales (Administrador, configuración, manuales y bitácora de la instalación) y carga
los exportados con los mismos IDs. Los intentos fallidos y los bloqueos se reinician.

Solo se exportan datos de prueba (la base de desarrollo no se modifica):
- Usuarios: solo las cuentas de CUENTAS_DE_PRUEBA, sin foto y con cambio obligatorio
  de contraseña. Lo que hizo otro Administrador sobre datos de prueba (talentos de
  ejemplo, manuales, alertas, configuración) queda a nombre del Administrador de prueba;
  lo de otros Encargados se quita.
- Talentos: solo los de datos_ejemplo.py (se reconocen por su alta en la bitácora),
  con sus evaluaciones y eventos.
- Notificaciones y bitácora: solo las que no mencionan a otras personas.
- Contacto de soporte: los valores de PRUEBA_SOPORTE.
"""

import datetime
import decimal
import json
from pathlib import Path

from backend import db, permisos

ARCHIVO = Path(__file__).parent / "database" / "datos_actuales.sql"

# Usuario -> datos que se reemplazan en la exportación
CUENTAS_DE_PRUEBA = {
    "AdminRH": {"nombre": "Administrador de prueba", "correo": "adminrh@correo.com"},
    "PruebaE": {"nombre": "Prueba Encargado", "correo": "prueba@correo.com"},
}
PRUEBA_SOPORTE = {"nombre_soporte": "Administrador de prueba",
                  "correo_soporte": "adminrh@correo.com",
                  "telefono_soporte": "1020304050"}

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
    return columnas, cursor.fetchall()


def _detalle(registro):
    try:
        return json.loads(registro["detalle"] or "{}")
    except ValueError:
        return {}


def talentos_de_ejemplo(bitacora):
    return {r["id_registro_afectado"] for r in bitacora
            if r["accion"] == "alta" and r["tabla_afectada"] == "Talentos"
            and _detalle(r).get("origen") == "datos_ejemplo.py"}


def limpiar(datos):
    # datos: {tabla: [registros]} -> mismos registros sin datos personales (ver el docstring)
    usuarios = {u["id_usuario"]: u for u in datos["Usuarios"]}
    prueba = {u["id_usuario"] for u in datos["Usuarios"] if u["usuario"] in CUENTAS_DE_PRUEBA}
    admin_prueba = next(i for i in prueba if usuarios[i]["cargo"] == permisos.ADMINISTRADOR)

    def reasignar(id_usuario):
        if id_usuario is None or id_usuario in prueba:
            return id_usuario
        if id_usuario in usuarios and usuarios[id_usuario]["cargo"] == permisos.ADMINISTRADOR:
            return admin_prueba
        return None

    # Textos que no deben quedar en ningún registro exportado
    prohibidos = [u[c] for u in datos["Usuarios"] for c in ("nombre", "usuario", "correo")
                  if u["id_usuario"] not in prueba]
    prohibidos += [usuarios[i][c] for i in prueba for c, nuevo in CUENTAS_DE_PRUEBA[usuarios[i]["usuario"]].items()
                   if usuarios[i][c] != nuevo]

    limpio = {}
    ejemplo = talentos_de_ejemplo(datos["Bitacora"])
    prohibidos += [t[c] for t in datos["Talentos"] if t["id_talento"] not in ejemplo
                   for c in ("nombre", "correo")]

    limpio["Usuarios"] = []
    for u in datos["Usuarios"]:
        if u["id_usuario"] in prueba:
            limpio["Usuarios"].append({**u, **CUENTAS_DE_PRUEBA[u["usuario"]], "foto": None,
                                       "debe_cambiar_contrasena": True,
                                       "intentos_fallidos": 0, "bloqueado_hasta": None})

    limpio["Talentos"] = [t for t in datos["Talentos"] if t["id_talento"] in ejemplo]
    limpio["Evaluaciones"] = [e for e in datos["Evaluaciones"] if e["id_talento"] in ejemplo]
    limpio["Eventos_talento"] = [{**e, "id_usuario_registro": reasignar(e["id_usuario_registro"])}
                                 for e in datos["Eventos_talento"] if e["id_talento"] in ejemplo]

    limpio["Manuales"] = [{**m, "id_usuario_edito": reasignar(m["id_usuario_edito"])}
                          for m in datos["Manuales"] if reasignar(m["id_usuario_edito"])]
    manuales = {m["id_manual"] for m in limpio["Manuales"]}
    limpio["Manual_imagenes"] = [i for i in datos["Manual_imagenes"] if i["id_manual"] in manuales]

    limpio["Notificaciones"] = []
    for n in datos["Notificaciones"]:
        if n["id_talento"] is not None and n["id_talento"] not in ejemplo:
            continue
        if n["tipo"] == "alerta_automatica":
            # Las genera el sistema: solo cambia el destinatario
            destinatario = reasignar(n["id_destinatario"])
            if destinatario:
                limpio["Notificaciones"].append({**n, "id_destinatario": destinatario})
        elif (n["tipo"] != "restablecer_acceso" and n["id_destinatario"] in prueba
              and n["id_emisor"] in prueba):
            # Mensajes escritos por personas: solo entre las cuentas de prueba
            limpio["Notificaciones"].append(n)
    notificaciones = {n["id_noti"] for n in limpio["Notificaciones"]}

    limpio["Alertas_config"] = [
        {**a, "id_usuario_creador": reasignar(a["id_usuario_creador"]),
         "id_destinatario": reasignar(a["id_destinatario"])}
        for a in datos["Alertas_config"]
        if reasignar(a["id_usuario_creador"]) and reasignar(a["id_destinatario"])
    ]
    alertas = {a["id_alerta"] for a in limpio["Alertas_config"]}

    limpio["Configuracion_sistema"] = [
        {**c, "valor": PRUEBA_SOPORTE.get(c["clave"], c["valor"]),
         "id_usuario_modifico": reasignar(c["id_usuario_modifico"])}
        for c in datos["Configuracion_sistema"]
    ]

    # Registros de la bitácora que se conservan, por tabla afectada
    permitidos = {"Usuarios": prueba, "Talentos": ejemplo, "Notificaciones": notificaciones,
                  "Alertas_config": alertas}
    limpio["Bitacora"] = []
    for r in datos["Bitacora"]:
        autor = reasignar(r["id_usuario"])
        tabla = r["tabla_afectada"]
        if autor is None:
            # Sin usuario (intentos con usuarios inexistentes) o de un Encargado que se quita
            continue
        if tabla in permitidos and r["id_registro_afectado"] not in permitidos[tabla]:
            continue
        if tabla == "Usuarios" and r["id_usuario"] not in prueba:
            # Sesiones y cambios de cuenta de otros usuarios
            continue
        if tabla == "Configuracion_sistema" and _detalle(r).get("clave") in PRUEBA_SOPORTE:
            # Guardan el contacto de soporte anterior
            continue
        limpio["Bitacora"].append({**r, "id_usuario": autor})

    revisar_prohibidos(limpio, [p for p in prohibidos if p and len(p) >= 4])
    return limpio


def revisar_prohibidos(datos, prohibidos):
    # Red de seguridad: ningún texto exportado debe contener datos de las personas quitadas
    for tabla, registros in datos.items():
        for registro in registros:
            for columna, valor in registro.items():
                if isinstance(valor, str):
                    for texto in prohibidos:
                        if texto.lower() in valor.lower():
                            raise ValueError(f"{tabla}.{columna} ({LLAVES[tabla]} = "
                                             f"{registro[LLAVES[tabla]]}) contiene «{texto}»")


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
        "-- manuales y bitácora de la instalación) y carga los de prueba con sus mismos",
        "-- IDs. Solo datos ficticios: las cuentas de prueba del README (con cambio",
        "-- obligatorio de contraseña) y los talentos generados con datos_ejemplo.py.",
        "-- =====================================================================",
        "",
        "SET NAMES utf8mb4;",
        "USE proyecto_talentos;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "START TRANSACTION;",
        "",
    ]
    partes += [f"DELETE FROM {tabla};" for tabla in reversed(TABLAS)]
    columnas, datos = {}, {}
    with db.transaccion() as cursor:
        for tabla in TABLAS:
            columnas[tabla], datos[tabla] = filas(cursor, tabla)
    datos = limpiar(datos)

    resumen = []
    for tabla in TABLAS:
        registros = datos[tabla]
        resumen.append((tabla, len(registros)))
        partes += ["", f"-- {tabla} ({len(registros)} registros)"]
        partes += list(inserts(tabla, columnas[tabla], registros))
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
