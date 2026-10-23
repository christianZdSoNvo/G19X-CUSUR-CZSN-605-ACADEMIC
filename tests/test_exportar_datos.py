import datetime
import decimal
import json

import pytest

import exportar_datos


def test_literales():
    assert exportar_datos.literal(None) == "NULL"
    assert exportar_datos.literal(42) == "42"
    assert exportar_datos.literal(decimal.Decimal("3.5")) == "3.5"
    assert exportar_datos.literal(datetime.date(2026, 10, 14)) == "'2026-10-14'"
    assert exportar_datos.literal(datetime.datetime(2026, 10, 14, 9, 5)) == "'2026-10-14 09:05:00'"
    assert exportar_datos.literal(b"\x89PNG") == "0x89504e47"
    assert exportar_datos.literal(b"") == "''"
    assert exportar_datos.literal('Dijo "sí" y l\'otro\\\n') == "'Dijo \"sí\" y l''otro\\\\\\n'"


def test_inserts_por_grupos():
    registros = [{"id": i, "nombre": f"T{i}"} for i in range(1, 121)]
    sentencias = list(exportar_datos.inserts("Talentos_x", ["id", "nombre"], registros))
    assert len(sentencias) == 3
    assert sentencias[0].startswith("INSERT INTO Talentos_x (id, nombre) VALUES\n    (1, 'T1'),")
    # Las tablas con imágenes van de una fila por sentencia
    assert len(list(exportar_datos.inserts("Manual_imagenes", ["id", "nombre"], registros[:3]))) == 3


def _usuario(id_usuario, usuario, cargo, nombre, correo):
    return {"id_usuario": id_usuario, "usuario": usuario, "cargo": cargo, "nombre": nombre, "correo": correo,
            "foto": b"\xff\xd8", "debe_cambiar_contrasena": False, "intentos_fallidos": 2, "bloqueado_hasta": None}


def _bitacora(id_bitacora, id_usuario, accion, tabla, id_registro, detalle=None):
    return {"id_bitacora": id_bitacora, "id_usuario": id_usuario, "accion": accion, "tabla_afectada": tabla,
            "id_registro_afectado": id_registro, "detalle": json.dumps(detalle) if detalle else None}


def _datos():
    return {
        "Usuarios": [
            _usuario(1, "Persona", "Administrador RH", "Persona Real", "persona@correo.com"),
            _usuario(4, "Otra", "Encargado de area", "Otra Persona", "otra@correo.com"),
            _usuario(76, "AdminRH", "Administrador RH", "Nombre Real Admin", "real.admin@correo.com"),
            _usuario(117, "PruebaE", "Encargado de area", "Prueba Encargado", "prueba@correo.com"),
        ],
        "Talentos": [{"id_talento": 9, "nombre": "Talento Real", "correo": "talento.real@correo.com"},
                     {"id_talento": 252, "nombre": "Ximena Rojas", "correo": "ximena@correo.com"}],
        "Evaluaciones": [{"id_evaluacion": 1, "id_talento": 9, "reporte_ia": "Talento Real destaca"},
                         {"id_evaluacion": 2, "id_talento": 252, "reporte_ia": "Ximena Rojas destaca"}],
        "Eventos_talento": [{"id_evento": 1, "id_talento": 252, "id_usuario_registro": 1},
                            {"id_evento": 2, "id_talento": 9, "id_usuario_registro": 1}],
        "Manuales": [{"id_manual": 1, "id_usuario_edito": 1}],
        "Manual_imagenes": [{"id_imagen": 1, "id_manual": 1}],
        "Notificaciones": [
            {"id_noti": 1, "id_emisor": None, "id_destinatario": 1, "id_talento": 252, "tipo": "alerta_automatica",
             "contenido": "Alerta: Ximena Rojas"},
            {"id_noti": 2, "id_emisor": None, "id_destinatario": 1, "id_talento": None, "tipo": "restablecer_acceso",
             "contenido": "Persona Real solicitó restablecer"},
            {"id_noti": 3, "id_emisor": 1, "id_destinatario": 4, "id_talento": None, "tipo": "otro",
             "contenido": "Mensaje personal"},
            {"id_noti": 4, "id_emisor": 117, "id_destinatario": 76, "id_talento": 252, "tipo": "correccion_datos",
             "contenido": "Corregir el desempeño"},
        ],
        "Bitacora": [
            _bitacora(1, 1, "alta", "Talentos", 252, {"origen": "datos_ejemplo.py"}),
            _bitacora(2, 1, "alta", "Talentos", 9, {"nuevo": {"nombre": "Talento Real"}}),
            _bitacora(3, 1, "inicio_sesion", "Usuarios", 1),
            _bitacora(4, None, "intento_fallido", "Usuarios", None, {"usuario": "PersonaReal"}),
            _bitacora(5, 1, "configuracion", "Configuracion_sistema", 1,
                      {"clave": "correo_soporte", "nuevo": "real@gmail.com"}),
            _bitacora(6, 76, "inicio_sesion", "Usuarios", 76),
            _bitacora(7, 4, "alta", "Alertas_config", 1),
            _bitacora(8, 1, "edicion", "Manuales", 1),
        ],
        "Alertas_config": [{"id_alerta": 1, "id_usuario_creador": 4, "id_destinatario": 4},
                           {"id_alerta": 2, "id_usuario_creador": 1, "id_destinatario": 1}],
        "Configuracion_sistema": [
            {"id_config": 1, "clave": "correo_soporte", "valor": "real@gmail.com", "id_usuario_modifico": 1},
            {"id_config": 2, "clave": "intentos_ia_por_dia", "valor": "3", "id_usuario_modifico": 1},
        ],
    }


def _ids(limpio, tabla):
    return [r[exportar_datos.LLAVES[tabla]] for r in limpio[tabla]]


def test_limpiar_deja_solo_datos_de_prueba():
    limpio = exportar_datos.limpiar(_datos())

    assert _ids(limpio, "Usuarios") == [76, 117]
    admin = limpio["Usuarios"][0]
    assert admin["nombre"] == "Administrador de prueba" and admin["correo"] == "adminrh@correo.com"
    assert all(u["foto"] is None and u["debe_cambiar_contrasena"] and u["intentos_fallidos"] == 0
               for u in limpio["Usuarios"])

    assert _ids(limpio, "Talentos") == [252]
    assert _ids(limpio, "Evaluaciones") == [2]
    assert _ids(limpio, "Eventos_talento") == [1]
    # Lo que hizo otro Administrador sobre datos de prueba pasa al Administrador de prueba
    assert limpio["Eventos_talento"][0]["id_usuario_registro"] == 76
    assert limpio["Manuales"][0]["id_usuario_edito"] == 76 and _ids(limpio, "Manual_imagenes") == [1]
    assert [(a["id_alerta"], a["id_destinatario"]) for a in limpio["Alertas_config"]] == [(2, 76)]

    assert _ids(limpio, "Notificaciones") == [1, 4]
    assert limpio["Notificaciones"][0]["id_destinatario"] == 76

    assert _ids(limpio, "Bitacora") == [1, 6, 8]
    assert limpio["Bitacora"][0]["id_usuario"] == 76
    assert exportar_datos.talentos_de_ejemplo(limpio["Bitacora"]) == {252}

    assert limpio["Configuracion_sistema"][0]["valor"] == "adminrh@correo.com"
    assert limpio["Configuracion_sistema"][1]["id_usuario_modifico"] == 76


def test_manuales_en_un_script_aparte():
    limpio = exportar_datos.limpiar(_datos())
    columnas = {tabla: list(registros[0]) for tabla, registros in limpio.items() if registros}
    principal, manuales = exportar_datos.scripts(columnas, limpio)

    # El volcado principal no toca los manuales: solo los pasa al Administrador de prueba
    assert "Manual" not in "".join(l for l in principal.splitlines() if l.startswith(("DELETE", "INSERT")))
    assert "UPDATE Manuales SET id_usuario_edito = 76;" in principal
    assert "ALTER TABLE Bitacora AUTO_INCREMENT = 9;" in principal
    # La bitácora de los manuales (id 8) va con ellos
    assert "INSERT INTO Bitacora" in principal and "    (8, " not in principal
    assert "DELETE FROM Manuales;" in manuales and "INSERT INTO Manual_imagenes" in manuales
    assert "DELETE FROM Bitacora WHERE id_bitacora IN (8);" in manuales
    assert "INSERT INTO Bitacora (id_bitacora, id_usuario, accion, tabla_afectada, id_registro_afectado, " \
           "detalle) VALUES\n    (8, 76, 'edicion', 'Manuales', 1, NULL);" in manuales
    assert "FOREIGN_KEY_CHECKS" not in manuales


def test_limpiar_se_detiene_si_queda_un_dato_personal():
    datos = _datos()
    datos["Evaluaciones"][1]["reporte_ia"] = "Comparado con Persona Real, destaca"
    with pytest.raises(ValueError, match="Persona Real"):
        exportar_datos.limpiar(datos)
