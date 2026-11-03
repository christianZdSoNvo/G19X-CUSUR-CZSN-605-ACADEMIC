import mysql.connector
import pytest

from backend import db, errores


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
