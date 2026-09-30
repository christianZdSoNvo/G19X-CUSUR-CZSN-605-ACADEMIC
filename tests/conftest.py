import time

import pytest
from streamlit.testing.v1 import AppTest

from backend import db, ia, permisos


@pytest.fixture(autouse=True)
def sin_precarga(monkeypatch):
    # Las pruebas no deben cargar el modelo real en segundo plano
    monkeypatch.setattr(ia, "precargar", lambda: None)


# Pruebas con MySQL: todo corre en una sola conexión que se deshace al final
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


@pytest.fixture
def app_con_sesion():
    # Crea la app con una sesión ya iniciada del usuario indicado
    def crear(usuario):
        app = AppTest.from_file("../app.py", default_timeout=30)
        app.session_state["usuario"] = {**usuario, "debe_cambiar_contrasena": False, "minutos_inactividad": 30}
        app.session_state["ultimo_acceso"] = time.time()
        return app
    return crear
