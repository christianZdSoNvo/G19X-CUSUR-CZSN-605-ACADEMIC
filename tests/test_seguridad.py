import pytest

from backend import db, errores, seguridad


def test_hash_conocido():
    # SHA-256 de "abc" (salt "a" + contraseña "bc")
    assert seguridad.hashear("bc", "a") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_verificar():
    salt = seguridad.generar_salt()
    guardado = seguridad.hashear("Clave123", salt)
    assert seguridad.verificar("Clave123", salt, guardado)
    assert not seguridad.verificar("clave123", salt, guardado)


def test_salt():
    salt = seguridad.generar_salt()
    assert len(salt) == 16
    int(salt, 16)
    assert salt != seguridad.generar_salt()


@pytest.mark.parametrize("contrasena, problemas", [
    ("Clave123", 0),
    ("Cl4ve", 1),
    ("clave123", 1),
    ("CLAVE123", 1),
    ("ClaveSinNumero", 1),
    ("", 4),
])
def test_politica(contrasena, problemas):
    assert len(seguridad.validar_politica(contrasena)) == problemas


def test_hash_igual_al_de_mysql():
    # El Administrador inicial se crea con SHA2 de MySQL; Python debe calcular lo mismo
    try:
        with db.transaccion() as cursor:
            cursor.execute("SELECT SHA2(CONCAT(%s, %s), 256) AS h", ("0a1b2c3d4e5f6a7b", "Clave123"))
            hash_mysql = cursor.fetchone()["h"]
    except errores.ErrorSistema:
        pytest.skip("MySQL no disponible")
    assert seguridad.hashear("Clave123", "0a1b2c3d4e5f6a7b") == hash_mysql
