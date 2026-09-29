import time

import pytest
from streamlit.testing.v1 import AppTest

from backend import errores, menu, permisos

ADMINISTRADOR = {"id_usuario": 1, "cargo": permisos.ADMINISTRADOR, "area": "Recursos Humanos"}
ENCARGADO = {"id_usuario": 2, "cargo": permisos.ENCARGADO, "area": "Calidad"}

SOLO_ADMINISTRADOR = {"editar_talentos", "evaluar_ia", "gestion_usuarios", "parametros",
                      "editar_manuales", "bitacora"}


@pytest.mark.parametrize("funcion", permisos.MATRIZ)
def test_matriz(funcion):
    assert permisos.puede(ADMINISTRADOR, funcion)
    assert permisos.puede(ENCARGADO, funcion) == (funcion not in SOLO_ADMINISTRADOR)


def test_exigir_lanza_e304():
    permisos.exigir(ADMINISTRADOR, "bitacora")
    with pytest.raises(errores.ErrorSistema) as error:
        permisos.exigir(ENCARGADO, "bitacora")
    assert error.value.codigo == "E-304"


def test_alcance_por_area():
    assert permisos.area_permitida(ADMINISTRADOR) is None
    assert permisos.area_permitida(ENCARGADO) == "Calidad"
    permisos.exigir_area(ADMINISTRADOR, "Finanzas")
    permisos.exigir_area(ENCARGADO, "Calidad")
    with pytest.raises(errores.ErrorSistema):
        permisos.exigir_area(ENCARGADO, "Finanzas")


def test_menu_segun_rol():
    visibles = lambda usuario: {titulo for _, _, titulo, _, visible in menu.opciones(usuario) if visible}
    solo_administrador = {"Gestión de usuarios", "Parámetros del sistema", "Bitácora"}
    assert solo_administrador <= visibles(ADMINISTRADOR)
    assert not solo_administrador & visibles(ENCARGADO)
    assert {"Talentos", "Manuales"} <= visibles(ENCARGADO)


def _app_con_sesion(usuario):
    app = AppTest.from_file("../app.py")
    app.session_state["usuario"] = {**usuario, "nombre": "Prueba", "debe_cambiar_contrasena": False,
                                    "minutos_inactividad": 30}
    app.session_state["ultimo_acceso"] = time.time()
    return app


def test_encargado_en_seccion_no_permitida_ve_e304():
    app = _app_con_sesion(ENCARGADO).run()
    app.switch_page("paginas/bitacora.py").run()
    assert not app.exception
    assert app.error[0].value == errores.CATALOGO["E-304"]
    next(boton for boton in app.button if boton.label == "Volver al inicio").click().run()
    assert not app.exception
    assert app.title[0].value == "Inicio"


def test_administrador_entra_a_seccion_propia():
    app = _app_con_sesion(ADMINISTRADOR).run()
    app.switch_page("paginas/bitacora.py").run()
    assert not app.exception
    assert not app.error
    assert app.title[0].value == "Bitácora"


@pytest.mark.parametrize("actual, nueva, confirmar, mensaje", [
    ("", "Nueva1234", "Nueva1234", "Escriba su contraseña actual."),
    ("Actual123", "Nueva1234", "Otra12345", "Las contraseñas no coinciden."),
])
def test_cambio_voluntario_valida_antes_de_consultar_la_bd(actual, nueva, confirmar, mensaje):
    app = _app_con_sesion(ENCARGADO).run()
    app.switch_page("paginas/configuracion.py").run()
    for campo, valor in zip(app.text_input, (actual, nueva, confirmar)):
        campo.input(valor)
    next(boton for boton in app.button if boton.label == "Guardar").click().run()
    assert not app.exception
    assert [error.value for error in app.error] == [mensaje]
