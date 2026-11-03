import importlib

import mysql.connector
import pytest

from backend import config, db, errores


@pytest.mark.parametrize("valor, puerto", [(None, 3306), ("3307", 3307)])
def test_puerto_de_mysql_desde_env(monkeypatch, valor, puerto):
    # Sin DB_PORT en el .env se usa el 3306
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    if valor is None:
        monkeypatch.delenv("DB_PORT", raising=False)
    else:
        monkeypatch.setenv("DB_PORT", valor)
    try:
        assert importlib.reload(config).DB_PORT == puerto
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_la_conexion_usa_el_puerto(monkeypatch):
    recibidos = {}
    monkeypatch.setattr(config, "DB_PORT", 3307)
    monkeypatch.setattr(mysql.connector, "connect", lambda **parametros: recibidos.update(parametros))
    db.obtener_conexion()
    assert recibidos["port"] == 3307 and recibidos["host"] == config.DB_HOST


@pytest.mark.parametrize("error, codigo", [
    (mysql.connector.InterfaceError(errno=2003), "E-001"),
    (mysql.connector.ProgrammingError(errno=1045), "E-002"),
    (mysql.connector.ProgrammingError(errno=1049), "E-002"),
    (mysql.connector.IntegrityError(errno=1062), "E-004"),
    (mysql.connector.IntegrityError(errno=1452), "E-003"),
    (mysql.connector.DatabaseError(errno=3819), "E-003"),
])
def test_codigo_de_error(error, codigo):
    assert db.codigo_de_error(error) == codigo


def test_catalogo_completo():
    assert len(errores.CATALOGO) == 16
    assert errores.ErrorSistema("E-301").mensaje == "Usuario o contraseña incorrectos."


def test_mensaje_con_datos():
    # E-302 ya no lleva los minutos escritos fijos: los recibe al lanzarse
    assert "15 minutos" not in errores.CATALOGO["E-302"]
    error = errores.ErrorSistema("E-302", tiempo="5 minutos")
    assert error.mensaje == "Cuenta bloqueada temporalmente. Intente en 5 minutos."
    assert "Intente en 5 minutos" in str(error)
    error = errores.ErrorSistema("E-101", errores.MODELO_NO_DESCARGADO, modelo="llama3.2:3b")
    assert error.mensaje == "El modelo de IA llama3.2:3b no está descargado. Ejecute: ollama pull llama3.2:3b"
