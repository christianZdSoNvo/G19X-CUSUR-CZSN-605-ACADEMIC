import datetime
import json

import pytest

from backend import alertas, db, errores, evaluaciones, ia, notificaciones, permisos, talentos

TALENTO = {"nombre": "Luis Pérez", "area": "Calidad", "correo": "luis.alertas@ejemplo.com",
           "tel_mx": "5511112222", "fecha_ingreso": datetime.date(2022, 1, 10), "desempeno_previo": 80,
           "competencias": "Pruebas", "capacitacion": "", "experiencia": "", "objetivos_futuros": "",
           "liderazgo_previo": ""}
VALIDA = {"desempeno_pre_ev": "alto", "resultados_cap_ev": "medio", "experiencia_lab_ev": "alto",
          "objetivos_fut_ev": "medio", "competencias_ev": "alto", "liderazgo_prev_ev": "bajo",
          "potencial_crecimiento_nivel": "alto", "puntuacion_talento_por_ia": 85, "reporte_ia": "Luis Pérez destaca."}


# --- Reglas (cálculo puro) ---

@pytest.mark.parametrize("condicion, anterior, nuevo, esperado", [
    ("disminuye", 80, 70, True), ("disminuye", 80, 71, False), ("disminuye", 70, 80, False),
    ("aumenta", 60, 70, True), ("aumenta", 60, 69, False),
    ("cambia", 50, 40, True), ("cambia", 50, 60, True), ("cambia", 50, 55, False),
    ("cambia", None, 50, False),
])
def test_variacion_de_puntos(condicion, anterior, nuevo, esperado):
    regla = {"indicador": "puntuacion_ia", "condicion": condicion, "umbral": 10}
    assert alertas.se_cumple(regla, anterior, nuevo) is esperado


@pytest.mark.parametrize("condicion, anterior, nuevo, esperado", [
    ("cambia", "alto", "medio", True), ("cambia", "medio", "medio", False),
    ("disminuye", "alto", "bajo", True), ("disminuye", "bajo", "medio", False),
    ("aumenta", "bajo", "medio", True), ("aumenta", "alto", "medio", False),
])
def test_cambio_de_nivel(condicion, anterior, nuevo, esperado):
    regla = {"indicador": "nivel_potencial", "condicion": condicion, "umbral": None}
    assert alertas.se_cumple(regla, anterior, nuevo) is esperado


def test_descripcion():
    assert alertas.descripcion({"indicador": "puntuacion_ia", "condicion": "disminuye", "umbral": 10}) == \
        "Puntuación de IA disminuye 10 puntos o más"
    assert alertas.descripcion({"indicador": "sin_evaluacion", "condicion": "dias_sin_evaluar", "umbral": 90}) == \
        "90 días o más sin evaluación"


def test_texto_de_la_notificacion():
    base = {"destinatario": "Ana López", "grado_emergencia": "alto", "contenido": "Revisar a Luis.",
            "emisor": None, "tipo": "alerta_automatica"}
    assert notificaciones.texto(base) == "Ana López [IMPORTANCIA: ALTO]\n\nRevisar a Luis.\n\nEmisor: Sistema"
    assert notificaciones.texto({**base, "tipo": "restablecer_acceso"}).endswith(
        "Emisor: Solicitud desde inicio de sesión")
    assert notificaciones.texto({**base, "emisor": "Carlos Ruiz"}).endswith("Emisor: Carlos Ruiz")


# --- Con MySQL (sin dejar rastro) ---

@pytest.fixture
def encargado(administrador):
    # Encargado real de Calidad, creado dentro de la transacción de la prueba
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Usuarios (cargo, area, nombre, usuario, correo, contrasena, salt, fecha_cambio_contrasena, "
            "debe_cambiar_contrasena, tel_mx) VALUES (%s, 'Calidad', 'Encargada Pytest', 'enc_pytest', "
            "'enc.pytest@ejemplo.com', 'x', '0123456789abcdef', CURDATE(), FALSE, '5500000000')",
            (permisos.ENCARGADO,),
        )
        id_usuario = cursor.lastrowid
    return {"id_usuario": id_usuario, "cargo": permisos.ENCARGADO, "area": "Calidad", "nombre": "Encargada Pytest"}


@pytest.fixture
def talento(administrador):
    _, id_talento = talentos.crear(administrador, TALENTO)
    return id_talento


def _notificaciones(id_destinatario, tipo="alerta_automatica"):
    with db.transaccion() as cursor:
        cursor.execute("SELECT * FROM Notificaciones WHERE id_destinatario = %s AND tipo = %s ORDER BY id_noti",
                       (id_destinatario, tipo))
        return cursor.fetchall()


def _regla(usuario, **cambios):
    datos = {"nombre": "Regla pytest", "indicador": "puntuacion_ia", "condicion": "cambia", "umbral": 10,
             "area": None, "id_destinatario": usuario["id_usuario"], "grado_emergencia": "alto", "activa": True,
             **cambios}
    problemas, id_alerta = alertas.crear(usuario, datos)
    assert problemas == {}
    return id_alerta


def test_encargado_envia_al_administrador(administrador, encargado, talento):
    destinos = notificaciones.destinatarios(encargado)
    assert destinos and all(d["cargo"] == permisos.ADMINISTRADOR for d in destinos)
    datos = {"tipo": "reevaluacion", "id_destinatario": administrador["id_usuario"], "id_talento": talento,
             "grado_emergencia": "medio", "contenido": "Tomó un curso nuevo."}
    problemas, id_noti = notificaciones.enviar(encargado, datos)
    assert problemas == {} and id_noti
    recibida = next(n for n in notificaciones.recibidas(administrador) if n["id_noti"] == id_noti)
    assert recibida["emisor"] == "Encargada Pytest" and recibida["talento"] == "Luis Pérez"
    assert notificaciones.pendientes(administrador) >= 1

    assert notificaciones.marcar_revisada(administrador, id_noti, "Listo, se reevaluó.") is None
    enviada = next(n for n in notificaciones.enviadas(encargado) if n["id_noti"] == id_noti)
    assert enviada["estado"] == "revisado" and enviada["respuesta"] == "Listo, se reevaluó."
    # Ya revisada no se vuelve a marcar
    with pytest.raises(errores.ErrorSistema):
        notificaciones.marcar_revisada(administrador, id_noti)


def test_validaciones_al_enviar(administrador, encargado, talento):
    base = {"tipo": "correccion_datos", "id_destinatario": administrador["id_usuario"], "id_talento": None,
            "grado_emergencia": "bajo", "contenido": "  "}
    problemas, _ = notificaciones.enviar(encargado, base)
    assert set(problemas) == {"id_talento", "contenido"}
    # El Encargado no escribe a otro Encargado
    problemas, _ = notificaciones.enviar(encargado, {**base, "id_talento": talento, "contenido": "x",
                                                     "id_destinatario": encargado["id_usuario"]})
    assert "id_destinatario" in problemas


def test_encargado_no_usa_talentos_de_otra_area(administrador, encargado):
    _, ajeno = talentos.crear(administrador, {**TALENTO, "area": "Finanzas", "correo": "ajeno.alertas@ejemplo.com"})
    datos = {"tipo": "reevaluacion", "id_destinatario": administrador["id_usuario"], "id_talento": ajeno,
             "grado_emergencia": "bajo", "contenido": "x"}
    with pytest.raises(errores.ErrorSistema) as error:
        notificaciones.enviar(encargado, datos)
    assert error.value.codigo == "E-304"
    # Tampoco el Administrador puede mandarle a un Encargado datos de otra área
    problemas, _ = notificaciones.enviar(administrador, {**datos, "id_destinatario": encargado["id_usuario"]})
    assert "id_talento" in problemas


def test_encargado_solo_configura_su_area(administrador, encargado):
    datos = {"nombre": "Mía", "indicador": "desempeno_previo", "condicion": "disminuye", "umbral": 5,
             "area": "Finanzas", "id_destinatario": administrador["id_usuario"], "grado_emergencia": "medio"}
    problemas, id_alerta = alertas.crear(encargado, datos)
    assert problemas == {}
    regla = next(r for r in alertas.listar(encargado) if r["id_alerta"] == id_alerta)
    assert regla["area"] == "Calidad" and regla["id_destinatario"] == encargado["id_usuario"]
    # Una regla del Administrador para el Encargado: la ve, pero no la modifica
    id_ajena = _regla(administrador, area="Calidad", id_destinatario=encargado["id_usuario"])
    assert id_ajena in {r["id_alerta"] for r in alertas.listar(encargado)}
    with pytest.raises(errores.ErrorSistema) as error:
        alertas.eliminar(encargado, id_ajena)
    assert error.value.codigo == "E-304"
    # Para un Encargado, el área de la regla debe ser la suya
    problemas, _ = alertas.crear(administrador, {**datos, "area": None, "id_destinatario": encargado["id_usuario"]})
    assert "area" in problemas


def test_validaciones_de_reglas(administrador):
    base = {"nombre": "", "indicador": "puntuacion_ia", "condicion": "dias_sin_evaluar", "umbral": 0,
            "area": "Otra", "id_destinatario": administrador["id_usuario"], "grado_emergencia": "urgente"}
    problemas, _ = alertas.crear(administrador, base)
    assert set(problemas) == {"nombre", "condicion", "umbral", "area", "grado_emergencia"}


def test_editar_activar_y_eliminar(administrador):
    id_alerta = _regla(administrador)
    assert alertas.editar(administrador, id_alerta, {"nombre": "Renombrada", "indicador": "nivel_potencial",
                                                     "condicion": "cambia", "umbral": 99, "area": "Calidad",
                                                     "id_destinatario": administrador["id_usuario"],
                                                     "grado_emergencia": "bajo", "activa": True}) == {}
    regla = next(r for r in alertas.listar(administrador) if r["id_alerta"] == id_alerta)
    assert regla["nombre"] == "Renombrada" and regla["umbral"] is None  # el nivel no usa umbral
    alertas.cambiar_activa(administrador, id_alerta, False)
    assert not next(r for r in alertas.listar(administrador) if r["id_alerta"] == id_alerta)["activa"]
    alertas.eliminar(administrador, id_alerta)
    assert id_alerta not in {r["id_alerta"] for r in alertas.listar(administrador)}
    with db.transaccion() as cursor:
        cursor.execute("SELECT accion FROM Bitacora WHERE tabla_afectada = 'Alertas_config' "
                       "AND id_registro_afectado = %s ORDER BY id_bitacora", (id_alerta,))
        assert [f["accion"] for f in cursor.fetchall()] == ["alta", "edicion", "edicion", "eliminacion"]


def _evaluar(administrador, id_talento, monkeypatch, puntuacion, nivel):
    respuesta = {**VALIDA, "puntuacion_talento_por_ia": puntuacion, "potencial_crecimiento_nivel": nivel}
    monkeypatch.setattr(ia, "asegurar_carga", lambda: None)
    monkeypatch.setattr(ia, "pedir_evaluacion", lambda prompt, segundos: json.dumps(respuesta))
    evaluaciones.evaluar(administrador, id_talento)


def test_alertas_al_evaluar(administrador, encargado, talento, monkeypatch):
    _regla(administrador, nombre="Puntos", area="Calidad")
    _regla(administrador, nombre="Nivel", indicador="nivel_potencial", condicion="disminuye", umbral=None)
    _regla(encargado, nombre="Mía")                                   # Calidad, para el Encargado
    _regla(administrador, nombre="Otra área", area="Finanzas")        # no aplica
    _regla(administrador, nombre="Inactiva", activa=False)            # no aplica
    antes = len(_notificaciones(administrador["id_usuario"]))

    _evaluar(administrador, talento, monkeypatch, 85, "alto")        # primera: sin comparación
    assert len(_notificaciones(administrador["id_usuario"])) == antes
    _evaluar(administrador, talento, monkeypatch, 60, "medio")       # -25 puntos y baja de nivel
    nuevas = _notificaciones(administrador["id_usuario"])[antes:]
    assert sorted(n["contenido"].split('"')[1] for n in nuevas) == ["Nivel", "Puntos"]
    assert all(n["id_emisor"] is None and n["id_talento"] == talento and n["grado_emergencia"] == "alto"
               for n in nuevas)
    assert "pasó de 85 a 60 puntos" in next(n["contenido"] for n in nuevas if "Puntos" in n["contenido"])
    assert len(_notificaciones(encargado["id_usuario"])) == 1


def test_alerta_al_editar_desempeno(administrador, talento):
    _regla(administrador, nombre="Desempeño", indicador="desempeno_previo", condicion="disminuye", umbral=10)
    antes = len(_notificaciones(administrador["id_usuario"]))
    talento_actual = talentos.obtener(administrador, talento)
    assert talentos.editar(administrador, talento, {**talento_actual, "desempeno_previo": 75}) == {}
    assert len(_notificaciones(administrador["id_usuario"])) == antes      # bajó solo 5
    assert talentos.editar(administrador, talento, {**talento_actual, "desempeno_previo": 60}) == {}
    nuevas = _notificaciones(administrador["id_usuario"])[antes:]
    assert len(nuevas) == 1 and "pasó de 75 a 60" in nuevas[0]["contenido"]


def test_dias_sin_evaluar_una_vez_por_talento(administrador, talento):
    _regla(administrador, nombre="Sin evaluar pytest", indicador="sin_evaluacion", condicion="dias_sin_evaluar",
           umbral=30, area="Calidad")

    def mias():
        return [n for n in _notificaciones(administrador["id_usuario"])
                if n["id_talento"] == talento and "Sin evaluar pytest" in n["contenido"]]

    alertas.revisar_sin_evaluar()
    assert len(mias()) == 1 and "desde su ingreso" in mias()[0]["contenido"]
    alertas.revisar_sin_evaluar()                                          # no se repite
    assert len(mias()) == 1


def test_bandeja_en_pantalla(administrador, encargado, talento, app_con_sesion):
    notificaciones.enviar(encargado, {"tipo": "otro", "id_destinatario": administrador["id_usuario"],
                                      "id_talento": None, "grado_emergencia": "alto", "contenido": "Hola"})
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/notificaciones.py").run()
    assert not app.exception
    assert [pestana.label for pestana in app.tabs] == ["Bandeja", "Nueva notificación", "Alertas"]


def test_encargado_en_pantalla(encargado, app_con_sesion):
    app = app_con_sesion(encargado).run()
    app.switch_page("paginas/notificaciones.py").run()
    assert not app.exception
    fijos = [campo.value for campo in app.text_input if campo.disabled]
    assert "Calidad" in fijos and "Encargada Pytest" in fijos


def test_solicitud_desde_talentos(encargado, talento, app_con_sesion):
    app = app_con_sesion(encargado).run()
    app.switch_page("paginas/talentos.py").run()
    app.selectbox(key="talentos_elegido").set_value(talento).run()
    app.button(key="solicitar_reevaluacion").click().run()
    assert not app.exception
    assert app.session_state["noti_tipo"] == "reevaluacion" and app.session_state["noti_talento"] == talento
    assert app.selectbox(key="noti_talento").value == talento
