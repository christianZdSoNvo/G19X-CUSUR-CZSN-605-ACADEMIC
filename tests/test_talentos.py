import datetime
import time

import pytest
from streamlit.testing.v1 import AppTest

from backend import db, errores, permisos, talentos

VALIDOS = {"nombre": "Luis Pérez", "area": "Calidad", "correo": "luis.pytest@ejemplo.com",
           "tel_mx": "5512345678", "fecha_ingreso": datetime.date(2024, 3, 1), "desempeno_previo": 80,
           "competencias": "Python", "capacitacion": "", "experiencia": "", "objetivos_futuros": "",
           "liderazgo_previo": ""}


def test_datos_validos():
    assert talentos.validar(talentos.limpiar(VALIDOS)) == {}


@pytest.mark.parametrize("campo, valor", [
    ("nombre", ""),
    ("nombre", "x" * 51),
    ("area", "Marketing"),
    ("correo", "luis@ejemplo"),
    ("tel_mx", "551234567"),
    ("fecha_ingreso", None),
    ("fecha_ingreso", datetime.date.today() + datetime.timedelta(days=1)),
    ("desempeno_previo", 101),
    ("desempeno_previo", -1),
    ("capacitacion", "x" * 401),
    ("objetivos_futuros", "x" * 201),
])
def test_datos_invalidos(campo, valor):
    assert list(talentos.validar(talentos.limpiar({**VALIDOS, campo: valor}))) == [campo]


def test_limpiar():
    datos = talentos.limpiar({**VALIDOS, "nombre": "  Luis ", "correo": " LUIS@Ejemplo.com ",
                              "desempeno_previo": 75.0, "experiencia": "   "})
    assert datos["nombre"] == "Luis"
    assert datos["correo"] == "luis@ejemplo.com"
    assert datos["desempeno_previo"] == 75
    assert datos["experiencia"] == talentos.SIN_REGISTRO


def test_desempeno_opcional():
    assert talentos.validar(talentos.limpiar({**VALIDOS, "desempeno_previo": None})) == {}


# --- Pruebas con MySQL: todo corre en una sola conexión que se deshace al final ---

class _SinConfirmar:
    def __init__(self, conexion):
        self._conexion = conexion

    def cursor(self, **opciones):
        return self._conexion.cursor(**opciones)

    def commit(self):
        pass

    def is_connected(self):
        return self._conexion.is_connected()

    def close(self):
        pass


@pytest.fixture
def administrador(monkeypatch):
    try:
        conexion = db.obtener_conexion()
    except Exception:
        pytest.skip("MySQL no disponible")
    monkeypatch.setattr(db, "obtener_conexion", lambda: _SinConfirmar(conexion))
    try:
        with db.transaccion() as cursor:
            cursor.execute("SELECT id_usuario FROM Usuarios WHERE cargo = %s LIMIT 1",
                           (permisos.ADMINISTRADOR,))
            fila = cursor.fetchone()
        yield {"id_usuario": fila["id_usuario"], "cargo": permisos.ADMINISTRADOR,
               "area": "Recursos Humanos", "nombre": "Prueba"}
    finally:
        conexion.rollback()
        conexion.close()


def _consultar(sql, parametros):
    with db.transaccion() as cursor:
        cursor.execute(sql, parametros)
        return cursor.fetchall()


def test_ciclo_completo(administrador):
    problemas, id_talento = talentos.crear(administrador, VALIDOS)
    assert problemas == {} and id_talento
    assert _consultar("SELECT tipo_evento FROM Eventos_talento WHERE id_talento = %s",
                      (id_talento,)) == [{"tipo_evento": "ingreso"}]

    # Correo repetido de un talento activo: E-004 en el campo
    problemas, _ = talentos.crear(administrador, {**VALIDOS, "nombre": "Otro"})
    assert problemas == {"correo": talentos.DUPLICADO}

    # Edición con eventos automáticos y valores anteriores en la bitácora
    assert talentos.editar(administrador, id_talento,
                           {**VALIDOS, "desempeno_previo": 65, "area": "Finanzas"}) == {}
    eventos = {fila["tipo_evento"] for fila in _consultar(
        "SELECT tipo_evento FROM Eventos_talento WHERE id_talento = %s", (id_talento,))}
    assert eventos == {"ingreso", "cambio_desempeno", "cambio_area"}
    ultima = _consultar("SELECT accion, detalle FROM Bitacora WHERE tabla_afectada = 'Talentos' "
                        "AND id_registro_afectado = %s ORDER BY id_bitacora DESC LIMIT 1", (id_talento,))[0]
    assert ultima["accion"] == "edicion" and '"desempeno_previo": 80' in ultima["detalle"]

    # Baja lógica: motivo obligatorio y deja de aparecer en la búsqueda
    assert "motivo" in talentos.dar_de_baja(administrador, id_talento, "  ")
    assert talentos.dar_de_baja(administrador, id_talento, "Renuncia voluntaria") == {}
    assert not talentos.buscar(administrador, str(id_talento))
    assert id_talento in {fila["id_talento"] for fila in talentos.listar_bajas(administrador)}

    # Alta con el correo de un talento dado de baja: se ofrece reactivarlo
    with pytest.raises(talentos.TalentoDeBaja) as de_baja:
        talentos.crear(administrador, VALIDOS)
    assert de_baja.value.id_talento == id_talento

    talentos.reactivar(administrador, id_talento)
    encontrado = talentos.buscar(administrador, str(id_talento))
    assert [fila["id_talento"] for fila in encontrado] == [id_talento]


def test_encargado_solo_ve_su_area(administrador):
    _, id_talento = talentos.crear(administrador, VALIDOS)
    encargado = {"id_usuario": administrador["id_usuario"], "cargo": permisos.ENCARGADO, "area": "Finanzas"}
    assert id_talento not in {fila["id_talento"] for fila in talentos.buscar(encargado, area="Calidad")}
    with pytest.raises(errores.ErrorSistema) as error:
        talentos.obtener(encargado, id_talento)
    assert error.value.codigo == "E-304"
    with pytest.raises(errores.ErrorSistema):
        talentos.crear(encargado, {**VALIDOS, "correo": "otro.pytest@ejemplo.com"})


def _app_con_sesion(usuario):
    app = AppTest.from_file("../app.py", default_timeout=30)
    app.session_state["usuario"] = {**usuario, "debe_cambiar_contrasena": False, "minutos_inactividad": 30}
    app.session_state["ultimo_acceso"] = time.time()
    return app


def test_pantalla_muestra_errores_debajo_de_los_campos(administrador):
    app = _app_con_sesion(administrador).run()
    app.switch_page("paginas/talentos.py").run()
    assert not app.exception
    assert [pestana.label for pestana in app.tabs] == ["Lista", "Nuevo talento", "Talentos dados de baja"]
    assert not app.warning
    app.text_input(key="nuevo_talento_tel_mx").input("123")
    next(boton for boton in app.button if boton.label == "Guardar").click().run()
    assert not app.exception
    mensajes = [error.value for error in app.error]
    assert "El teléfono debe tener 10 dígitos." in mensajes
    assert f"{errores.CATALOGO['E-003']} (E-003)" in mensajes


def test_edicion_y_baja_desde_la_pantalla(administrador):
    _, id_talento = talentos.crear(administrador, VALIDOS)
    app = _app_con_sesion(administrador).run()
    app.switch_page("paginas/talentos.py").run()
    app.text_input[0].input(str(id_talento)).run()
    app.selectbox[1].select(id_talento).run()
    clave = f"editar_{id_talento}"
    assert app.text_input(key=f"{clave}_nombre").value == VALIDOS["nombre"]
    assert app.text_area(key=f"{clave}_capacitacion").value == ""
    assert not app.warning

    app.number_input(key=f"{clave}_desempeno_previo").set_value(90)
    next(boton for boton in app.button if boton.label == "Guardar").click().run()
    assert not app.exception
    assert app.success[0].value == f"Se actualizaron los datos de {VALIDOS['nombre']}."
    assert talentos.obtener(administrador, id_talento)["desempeno_previo"] == 90

    next(boton for boton in app.button if boton.label == "Dar de baja").click().run()
    app.text_area(key=f"baja_{id_talento}_motivo").input("Cambio de empresa")
    app.checkbox(key=f"baja_{id_talento}_ok").check().run()
    next(boton for boton in app.button if boton.label == "Confirmar baja").click().run()
    assert not app.exception
    assert app.success[0].value == f"Se dio de baja a {VALIDOS['nombre']}."
    assert not talentos.obtener(administrador, id_talento)["activo"]


def test_encargado_no_ve_el_formulario(administrador):
    encargado = {**administrador, "cargo": permisos.ENCARGADO, "area": "Calidad"}
    app = _app_con_sesion(encargado).run()
    app.switch_page("paginas/talentos.py").run()
    assert not app.exception
    assert not app.tabs
    assert "Guardar" not in [boton.label for boton in app.button]
    assert app.text_input[1].value == "Calidad" and app.text_input[1].disabled
