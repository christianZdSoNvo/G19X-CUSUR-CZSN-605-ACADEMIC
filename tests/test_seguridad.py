import base64
import hashlib

import pytest

from backend import auth, db, errores, seguridad, usuarios

SALT = "0a1b2c3d4e5f6a7b"


def test_hash_pbkdf2():
    guardado = seguridad.hashear("Clave123", SALT)
    esperado = base64.b64encode(hashlib.pbkdf2_hmac("sha256", b"Clave123", SALT.encode(), 600_000)).decode()
    assert guardado == f"pbkdf2_sha256$600000${esperado}"
    # Cabe en Usuarios.contrasena VARCHAR(70)
    assert len(guardado) <= 70


def test_verificar():
    salt = seguridad.generar_salt()
    guardado = seguridad.hashear("Clave123", salt)
    assert seguridad.verificar("Clave123", salt, guardado)
    assert not seguridad.verificar("clave123", salt, guardado)
    assert not seguridad.necesita_actualizar(guardado)


def test_verifica_el_formato_anterior():
    # SHA-256 de "abc" (salt "a" + contraseña "bc"), como lo guardaba la versión anterior
    anterior = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert seguridad.verificar("bc", "a", anterior)
    assert not seguridad.verificar("bd", "a", anterior)
    assert seguridad.necesita_actualizar(anterior)


def test_otras_iteraciones_se_actualizan():
    guardado = seguridad._pbkdf2("Clave123", SALT, 1000)
    assert seguridad.verificar("Clave123", SALT, guardado)
    assert seguridad.necesita_actualizar(guardado)


@pytest.mark.parametrize("guardado", [seguridad.PENDIENTE, "", "pbkdf2_sha256$abc$00", "x" * 70])
def test_valores_desconocidos_nunca_coinciden(guardado):
    assert not seguridad.verificar("Clave123", SALT, guardado)
    assert not seguridad.verificar("", SALT, guardado)


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


def test_contrasena_temporal_cumple_la_politica():
    for _ in range(200):
        temporal = seguridad.generar_temporal()
        assert len(temporal) == 10
        assert seguridad.validar_politica(temporal) == []


# --- Con MySQL (sin dejar rastro) ---

def _crear_usuario(contrasena, salt=SALT):
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Usuarios (cargo, area, nombre, usuario, correo, contrasena, salt, "
            "fecha_cambio_contrasena, debe_cambiar_contrasena, tel_mx) "
            "VALUES ('Encargado de area', 'Finanzas', 'Prueba hash', 'prueba_hash', "
            "'prueba.hash@correo.com', %s, %s, CURDATE(), FALSE, '1234567890')",
            (contrasena, salt),
        )
        return cursor.lastrowid


def _contrasena_guardada(id_usuario):
    with db.transaccion() as cursor:
        cursor.execute("SELECT contrasena, salt FROM Usuarios WHERE id_usuario = %s", (id_usuario,))
        return cursor.fetchone()


def test_inicio_de_sesion_actualiza_el_formato_anterior(administrador):
    id_usuario = _crear_usuario(hashlib.sha256((SALT + "Clave123").encode()).hexdigest())
    auth.iniciar_sesion("prueba_hash", "Clave123")

    fila = _contrasena_guardada(id_usuario)
    assert fila["contrasena"].startswith("pbkdf2_sha256$600000$")
    assert seguridad.verificar("Clave123", fila["salt"], fila["contrasena"])
    # La siguiente vez entra con el formato nuevo
    auth.iniciar_sesion("prueba_hash", "Clave123")


def test_administrador_pendiente_no_puede_entrar(administrador):
    id_usuario = _crear_usuario(seguridad.PENDIENTE)
    with pytest.raises(errores.ErrorSistema) as error:
        auth.iniciar_sesion("prueba_hash", seguridad.PENDIENTE)
    assert error.value.codigo == "E-301"

    # reset_admin.py usa restablecer_contrasena: la cuenta ya puede entrar
    temporal = usuarios.restablecer_contrasena(administrador, id_usuario, origen="reset_admin.py")
    assert _contrasena_guardada(id_usuario)["contrasena"].startswith("pbkdf2_sha256$")
    assert auth.iniciar_sesion("prueba_hash", temporal)["debe_cambiar_contrasena"]
