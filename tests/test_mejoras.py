"""Mejoras de Agregados.txt: accesos de Inicio, fotos de perfil, contacto del talento y paneles."""

import datetime
import io
import json

import pytest
from PIL import Image

from backend import db, errores, evaluaciones, fotos, menu, permisos, reportes, talentos, usuarios

ADMINISTRADOR = {"id_usuario": 1, "cargo": permisos.ADMINISTRADOR, "area": "Recursos Humanos"}
ENCARGADO = {"id_usuario": 2, "cargo": permisos.ENCARGADO, "area": "Calidad"}
TALENTO = {"nombre": "Foto Pytest", "area": "Calidad", "correo": "foto.pytest@ejemplo.com",
           "tel_mx": "5511112222", "fecha_ingreso": datetime.date(2024, 1, 15), "desempeno_previo": 70}


def _imagen(formato="PNG", tamano=(800, 500)):
    salida = io.BytesIO()
    Image.new("RGB", tamano, (201, 162, 39)).save(salida, formato)
    return salida.getvalue()


# --- Inicio: las secciones del menú como accesos ---

def test_accesos_de_inicio_por_rol():
    def archivos(usuario):
        return {archivo for opciones in menu.accesos(usuario).values() for archivo, _, _ in opciones}

    administrador, encargado = archivos(ADMINISTRADOR), archivos(ENCARGADO)
    assert "paginas/inicio.py" not in administrador
    assert {"paginas/gestion_usuarios.py", "paginas/bitacora.py", "paginas/parametros.py"} <= administrador
    assert not {"paginas/gestion_usuarios.py", "paginas/bitacora.py", "paginas/parametros.py"} & encargado
    assert {"paginas/talentos.py", "paginas/notificaciones.py", "paginas/soporte.py"} <= encargado
    assert list(menu.accesos(ENCARGADO)) == ["Talentos", "Seguimiento", "Configuración", "Ayuda"]


def test_accesos_de_inicio_con_pendientes():
    titulos = [titulo for opciones in menu.accesos(ENCARGADO, pendientes=3).values() for _, titulo, _ in opciones]
    assert "Notificaciones y alertas (3)" in titulos


# --- Fotos de perfil ---

@pytest.mark.parametrize("formato", ["PNG", "JPEG"])
def test_preparar_foto(formato):
    foto = fotos.preparar(_imagen(formato))
    imagen = Image.open(io.BytesIO(foto))
    assert imagen.format == "JPEG" and imagen.size == (fotos.LADO, fotos.LADO)


@pytest.mark.parametrize("contenido", [b"no es una imagen", b"\x89PNG\r\n\x1a\n" + b"0" * 100])
def test_foto_invalida_da_e402(contenido):
    with pytest.raises(errores.ErrorSistema) as error:
        fotos.preparar(contenido)
    assert error.value.codigo == "E-402"


def test_foto_mayor_a_5_mb_da_e402():
    with pytest.raises(errores.ErrorSistema) as error:
        fotos.preparar(b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024))
    assert error.value.codigo == "E-402"


def _bitacora_foto(tabla, id_registro):
    with db.transaccion() as cursor:
        cursor.execute("SELECT accion, detalle FROM Bitacora WHERE tabla_afectada = %s AND id_registro_afectado = %s "
                       "ORDER BY id_bitacora DESC LIMIT 1", (tabla, id_registro))
        fila = cursor.fetchone()
    return fila["accion"], json.loads(fila["detalle"])


def test_foto_de_talento(administrador):
    _, id_talento = talentos.crear(administrador, TALENTO)
    assert talentos.obtener(administrador, id_talento)["foto"] is None

    talentos.cambiar_foto(administrador, id_talento, _imagen())
    assert Image.open(io.BytesIO(talentos.obtener(administrador, id_talento)["foto"])).size == (400, 400)
    assert _bitacora_foto("Talentos", id_talento) == ("edicion", {"foto": "actualizada"})

    talentos.cambiar_foto(administrador, id_talento, None)
    assert talentos.obtener(administrador, id_talento)["foto"] is None
    assert _bitacora_foto("Talentos", id_talento) == ("edicion", {"foto": "eliminada"})


def test_cambiar_foto_no_renueva_intentos_de_ia(administrador):
    _, id_talento = talentos.crear(administrador, TALENTO)
    with db.transaccion() as cursor:
        # Un intento de hoy después del alta
        cursor.execute("INSERT INTO Bitacora (id_usuario, fecha_hora, accion, tabla_afectada, id_registro_afectado, "
                       "detalle) VALUES (%s, NOW(), 'evaluacion_ia', 'Talentos', %s, %s)",
                       (administrador["id_usuario"], id_talento, json.dumps({"intentos": 1})))
    talentos.cambiar_foto(administrador, id_talento, _imagen())
    assert evaluaciones.estado(id_talento)["usados"] == 1

    # Una edición de sus datos sí los renueva (PRD, 10)
    talentos.editar(administrador, id_talento, {**TALENTO, "desempeno_previo": 75})
    assert evaluaciones.estado(id_talento)["usados"] == 0


def test_encargado_no_cambia_fotos_de_talentos():
    with pytest.raises(errores.ErrorSistema) as error:
        talentos.cambiar_foto(ENCARGADO, 1, None)
    assert error.value.codigo == "E-304"


def test_foto_de_usuario(administrador):
    nueva = usuarios.cambiar_foto(administrador, _imagen("JPEG"))
    assert usuarios.foto(administrador["id_usuario"]) == nueva
    assert _bitacora_foto("Usuarios", administrador["id_usuario"]) == ("edicion", {"foto": "actualizada"})
    assert usuarios.cambiar_foto(administrador, None) is None
    assert usuarios.foto(administrador["id_usuario"]) is None


def test_pdf_individual_con_foto(administrador):
    _, id_talento = talentos.crear(administrador, TALENTO)
    for foto in (None, _imagen()):
        talentos.cambiar_foto(administrador, id_talento, foto)
        resultado = reportes.exportar(administrador, reportes.datos_individual(administrador, id_talento), "pdf")
        assert resultado["codigo"] is None and resultado["contenido"].startswith(b"%PDF")


# --- Pantallas ---

def test_inicio_muestra_las_secciones(app_con_sesion):
    app = app_con_sesion({**ENCARGADO, "nombre": "Prueba"}).run()
    assert not app.exception
    assert app.title[0].value == "Inicio"
    etiquetas = [enlace.label for enlace in app.get("page_link")]
    assert "Talentos" in etiquetas and "Soporte" in etiquetas
    assert "Bitácora" not in etiquetas and "Gestión de usuarios" not in etiquetas


def test_paneles_elegidos_en_el_menu(app_con_sesion):
    app = app_con_sesion({**ADMINISTRADOR, "nombre": "Prueba"}).run()
    # El selector de paneles solo aparece en la página de Paneles analíticos
    assert not [pills for pills in app.sidebar.get("button_group") if pills.label == "Paneles a mostrar"]
    app.switch_page("paginas/paneles.py").run()
    assert not app.exception
    selector = next(pills for pills in app.sidebar.get("button_group") if pills.label == "Paneles a mostrar")
    textos = [markdown.value for markdown in app.markdown]
    assert "**Matriz 9-box**" in textos and "**Histograma de puntuaciones de IA**" in textos
    selector.set_value(["Matriz 9-box", "Evolución mensual"]).run()
    assert not app.exception
    textos = [markdown.value for markdown in app.markdown]
    assert "**Matriz 9-box**" in textos and "**Evolución mensual del promedio de puntuación**" in textos
    assert "**Histograma de puntuaciones de IA**" not in textos


def test_menu_de_la_barra_lateral_por_rol(app_con_sesion):
    app = app_con_sesion({**ENCARGADO, "nombre": "Prueba"}).run()
    etiquetas = [enlace.label for enlace in app.sidebar.get("page_link")]
    assert "Paneles analíticos" in etiquetas and "Soporte" in etiquetas
    assert "Bitácora" not in etiquetas and "Parámetros del sistema" not in etiquetas


def test_nueva_notificacion_queda_en_blanco_al_enviar(app_con_sesion, monkeypatch):
    from backend import notificaciones
    monkeypatch.setattr(notificaciones, "enviar", lambda usuario, datos: ({}, 1))
    app = app_con_sesion({**ADMINISTRADOR, "nombre": "Prueba"}).run()
    app.switch_page("paginas/notificaciones.py").run()
    app.selectbox(key="noti_destinatario").select_index(0)
    app.segmented_control(key="noti_grado").set_value("alto")
    app.text_area(key="noti_texto").input("Texto privado de prueba").run()
    next(boton for boton in app.button if boton.label == "Enviar").click().run()
    assert not app.exception
    assert app.success[0].value.startswith("Se envió la notificación")
    assert app.text_area(key="noti_texto").value == ""
    assert app.selectbox(key="noti_destinatario").value is None
    assert app.segmented_control(key="noti_grado").value == "bajo"
