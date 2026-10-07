import datetime
import io
import json
from urllib.parse import unquote

import pytest
from PIL import Image

from backend import auth, bitacora, db, errores, evaluaciones, manuales, parametros, permisos, vistas


def _png(lado=4):
    salida = io.BytesIO()
    Image.new("RGB", (lado, lado), "#C9A227").save(salida, format="PNG")
    return salida.getvalue()


def _bitacora(accion, tabla):
    with db.transaccion() as cursor:
        cursor.execute("SELECT * FROM Bitacora WHERE accion = %s AND tabla_afectada = %s "
                       "ORDER BY id_bitacora DESC LIMIT 1", (accion, tabla))
        return cursor.fetchone()


@pytest.fixture
def encargado(administrador):
    return {**administrador, "cargo": permisos.ENCARGADO, "area": "Calidad"}


# --- Parámetros del sistema ---

@pytest.mark.parametrize("clave, valor, valido", [
    ("tiempo_max_ia_seg", "90", True), ("tiempo_max_ia_seg", "29", False), ("tiempo_max_ia_seg", "601", False),
    ("intentos_ia_por_dia", "3", True), ("intentos_ia_por_dia", "0", False), ("intentos_ia_por_dia", "2.5", False),
    ("max_intentos_login", "abc", False), ("minutos_inactividad_sesion", "5", True),
    ("correo_soporte", "soporte@empresa.com", True), ("correo_soporte", "soporte", False),
    ("correo_soporte", "Por definir", True), ("telefono_soporte", "5512345678", True),
    ("telefono_soporte", "55123", False), ("nombre_soporte", "", False), ("nombre_soporte", "x" * 101, False),
])
def test_validar_parametros(clave, valor, valido):
    assert (parametros.validar({clave: valor}) == {}) is valido


def test_soporte_vacio_queda_por_definir():
    assert parametros.limpiar({"telefono_soporte": " ", "nombre_soporte": None}) == {
        "telefono_soporte": "Por definir", "nombre_soporte": "Por definir"}


def test_guardar_aplica_y_registra(administrador):
    problemas, cambiados = parametros.guardar(administrador, {
        "intentos_ia_por_dia": 7, "max_intentos_login": "4", "correo_soporte": " soporte@empresa.com ",
    })
    assert problemas == {}
    registro = _bitacora("configuracion", "Configuracion_sistema")
    assert registro["id_usuario"] == administrador["id_usuario"]
    assert set(cambiados) <= {"intentos_ia_por_dia", "max_intentos_login", "correo_soporte"}

    # El cambio se aplica: los módulos leen el valor nuevo en su siguiente operación
    assert evaluaciones.estado(0)["limite"] == 7
    with db.transaccion() as cursor:
        assert auth._parametros(cursor)["max_intentos_login"] == 4
    assert parametros.contacto_soporte()["correo"] == "soporte@empresa.com"

    # Sin cambios no se registra nada
    _, cambiados = parametros.guardar(administrador, {"intentos_ia_por_dia": 7})
    assert cambiados == []


def test_bitacora_guarda_anterior_y_nuevo(administrador):
    anterior = parametros.obtener(["minutos_bloqueo"])["minutos_bloqueo"]
    nuevo = "20" if anterior != "20" else "25"
    parametros.guardar(administrador, {"minutos_bloqueo": nuevo})
    detalle = json.loads(_bitacora("configuracion", "Configuracion_sistema")["detalle"])
    assert detalle == {"clave": "minutos_bloqueo", "anterior": anterior, "nuevo": nuevo}


def test_guardar_invalido_no_cambia_nada(administrador):
    antes = parametros.obtener()
    problemas, cambiados = parametros.guardar(administrador, {"intentos_ia_por_dia": "8", "tiempo_max_ia_seg": "5"})
    assert set(problemas) == {"tiempo_max_ia_seg"} and cambiados == []
    assert parametros.obtener() == antes


def test_encargado_no_cambia_parametros(encargado):
    with pytest.raises(errores.ErrorSistema) as error:
        parametros.guardar(encargado, {"intentos_ia_por_dia": "8"})
    assert error.value.codigo == "E-304"


# --- Manuales ---

def test_validar_imagen():
    manuales.validar_imagen(_png())
    manuales.validar_imagen(b"\xff\xd8\xff\xe0" + b"0" * 100)
    for contenido in (b"GIF89a....", b"%PDF-1.7", b"\x89PNG\r\n\x1a\n" + b"0" * manuales.MAX_IMAGEN):
        with pytest.raises(errores.ErrorSistema) as error:
            manuales.validar_imagen(contenido)
        assert error.value.codigo == "E-402"


def test_validar_manual():
    vacio = manuales.limpiar({"seccion_software": "Reportes"})
    assert set(manuales.validar(vacio, con_imagen=False)) == {"contenido_texto"}
    assert manuales.validar(vacio, con_imagen=True) == {}
    malo = manuales.limpiar({"seccion_software": "Otra", "contenido_texto": "x", "contenido_enlace": "www.x.com"})
    assert set(manuales.validar(malo, con_imagen=False)) == {"seccion_software", "contenido_enlace"}


def test_secciones_del_encargado(administrador, encargado):
    assert manuales.secciones_permitidas(administrador) == list(manuales.SECCIONES)
    propias = manuales.secciones_permitidas(encargado)
    assert not {"Gestión de usuarios", "Parámetros del sistema", "Bitácora"} & set(propias)
    assert {"Inicio de sesión", "Talentos", "Reportes", "Soporte"} <= set(propias)


def test_crear_editar_eliminar(administrador, encargado):
    problemas, id_manual = manuales.crear(administrador, {
        "seccion_software": "Bitácora", "contenido_texto": "Manual pytest de la bitácora",
        "contenido_enlace": "https://ejemplo.com/manual"}, [_png(), _png(6)])
    assert problemas == {}
    alta = _bitacora("alta", "Manuales")
    assert alta["id_registro_afectado"] == id_manual and json.loads(alta["detalle"])["imagenes"] == 2

    # El Encargado no ve la sección Bitácora; el Administrador sí
    assert id_manual in [m["id_manual"] for m in manuales.listar(administrador, texto="pytest de la bit")]
    assert id_manual not in [m["id_manual"] for m in manuales.listar(encargado)]

    # Editar conserva las imágenes, agrega las nuevas al final y quita las que se piden
    def imagenes():
        manual = next(m for m in manuales.listar(administrador, "Bitácora") if m["id_manual"] == id_manual)
        return manual, [m["id_imagen"] for m in manual["imagenes"]]

    assert manuales.editar(administrador, id_manual, {"seccion_software": "Bitácora",
                                                      "contenido_texto": "Nuevo texto"}) == {}
    manual, ids = imagenes()
    assert len(ids) == 2 and manual["contenido_enlace"] is None
    assert manuales.editar(administrador, id_manual, {"seccion_software": "Bitácora", "contenido_texto": "x"},
                           nuevas=[_png(8)], quitar=[ids[0]]) == {}
    manual, nuevos_ids = imagenes()
    assert nuevos_ids[0] == ids[1] and len(nuevos_ids) == 2
    assert bytes(manual["imagenes"][1]["imagen"]) == _png(8)
    # Sin texto ni enlace, quitar todas las imágenes deja el manual vacío
    assert set(manuales.editar(administrador, id_manual, {"seccion_software": "Bitácora"},
                               quitar=nuevos_ids)) == {"contenido_texto"}
    # Máximo de imágenes por manual
    assert set(manuales.editar(administrador, id_manual, {"seccion_software": "Bitácora", "contenido_texto": "x"},
                               nuevas=[_png()] * (manuales.MAX_IMAGENES - 1))) == {"imagenes"}
    assert _bitacora("edicion", "Manuales")["id_registro_afectado"] == id_manual

    with pytest.raises(errores.ErrorSistema) as error:
        manuales.eliminar(encargado, id_manual)
    assert error.value.codigo == "E-304"
    manuales.eliminar(administrador, id_manual)
    assert id_manual not in [m["id_manual"] for m in manuales.listar(administrador)]
    with db.transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM Manual_imagenes WHERE id_manual = %s", (id_manual,))
        assert cursor.fetchone()["n"] == 0
    assert _bitacora("eliminacion", "Manuales")["id_registro_afectado"] == id_manual


def test_imagen_invalida_no_se_guarda(administrador):
    with pytest.raises(errores.ErrorSistema) as error:
        manuales.crear(administrador, {"seccion_software": "Reportes", "contenido_texto": "x"}, [_png(), b"GIF89a"])
    assert error.value.codigo == "E-402"


# --- Bitácora ---

def test_consultar_bitacora(administrador, encargado):
    hoy = datetime.date.today()
    parametros.guardar(administrador, {"nombre_soporte": "Soporte pytest"})
    filas = bitacora.consultar(administrador, hoy, hoy, administrador["id_usuario"], ["configuracion"])
    assert filas and all(f["accion"] == "configuracion" and f["id_usuario"] == administrador["id_usuario"]
                         for f in filas)
    assert filas[0]["fecha_hora"].date() == hoy
    assert not bitacora.consultar(administrador, hoy - datetime.timedelta(days=3650),
                                  hoy - datetime.timedelta(days=3649), acciones=["configuracion"])
    assert all(f["id_usuario"] is None for f in bitacora.consultar(administrador, hoy, hoy, bitacora.SIN_USUARIO))
    with pytest.raises(errores.ErrorSistema):
        bitacora.consultar(encargado, hoy, hoy)


# --- Soporte ---

def test_enlace_de_correo():
    enlace = vistas.enlace_correo("soporte@empresa.com", "E-101")
    assert enlace.startswith("mailto:soporte@empresa.com?subject=")
    assert "Soporte – TalentOS" in unquote(enlace)
    assert "Código de error: E-101" in unquote(enlace)
    assert "Código de error" not in unquote(vistas.enlace_correo("soporte@empresa.com"))


# --- Pantallas ---

def test_pantalla_de_parametros(administrador, app_con_sesion):
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/parametros.py").run()
    assert not app.exception and not app.error
    entrada = next(n for n in app.number_input if n.label == "Evaluaciones por talento al día")
    entrada.set_value(5)
    next(b for b in app.button if b.label == "Guardar").click().run()
    assert not app.exception
    assert not app.error
    assert app.success[0].value.startswith("Se guardaron")
    assert parametros.obtener(["intentos_ia_por_dia"])["intentos_ia_por_dia"] == "5"


def test_pantalla_de_parametros_invalida(administrador, app_con_sesion):
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/parametros.py").run()
    next(t for t in app.text_input if t.label == "Teléfono (10 dígitos)").input("123").run()
    next(b for b in app.button if b.label == "Guardar").click().run()
    assert app.error[0].value == "El teléfono debe tener 10 dígitos."


def test_pantallas_de_soporte_manuales_y_bitacora(administrador, encargado, app_con_sesion):
    for usuario in (administrador, encargado):
        app = app_con_sesion(usuario).run()
        for pagina, titulo in (("paginas/soporte.py", "Soporte"), ("paginas/manuales.py", "Manuales"),
                               ("paginas/configuracion.py", "Configuración")):
            app.switch_page(pagina).run()
            assert not app.exception, pagina
            assert app.title[0].value == titulo
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/bitacora.py").run()
    assert not app.exception and app.title[0].value == "Bitácora"


def test_sin_manuales_muestra_e401(administrador, app_con_sesion):
    with db.transaccion() as cursor:
        cursor.execute("DELETE FROM Manuales")
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/soporte.py").run()
    assert not app.exception
    assert app.warning[0].value.startswith("No hay manuales disponibles. Contacte a soporte:")


def test_selector_de_tema(administrador, app_con_sesion):
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/configuracion.py").run()
    assert not app.exception
    assert not [h for h in app.get("html") if "stMainMenuItem-theme" in h.proto.body]
    app.radio(key="tema").set_value("Oscuro").run()
    assert not app.exception
    scripts = [h.proto.body for h in app.get("html") if "stMainMenuItem-theme-Dark" in h.proto.body]
    assert len(scripts) == 1
    # En la siguiente ejecución ya no se vuelve a agregar el script
    app.run()
    assert not [h for h in app.get("html") if "stMainMenuItem-theme" in h.proto.body]
    assert app.radio(key="tema").value == "Oscuro"
