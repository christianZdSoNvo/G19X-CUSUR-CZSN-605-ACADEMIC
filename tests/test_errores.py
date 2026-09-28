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
