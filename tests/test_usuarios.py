import pytest

from backend import permisos, usuarios

VALIDOS = {"nombre": "Ana López", "usuario": "ana.lopez", "correo": "ana@empresa.com",
           "tel_mx": "5512345678", "cargo": permisos.ENCARGADO, "area": "Calidad"}


def test_datos_validos():
    assert usuarios.validar(VALIDOS) == []


@pytest.mark.parametrize("campo, valor", [
    ("nombre", ""),
    ("nombre", "x" * 51),
    ("usuario", "ab"),
    ("usuario", "ana lópez"),
    ("correo", "ana@empresa"),
    ("tel_mx", "551234567"),
    ("tel_mx", "55-1234-567"),
    ("cargo", "Talento"),
    ("area", ""),
])
def test_datos_invalidos(campo, valor):
    assert len(usuarios.validar({**VALIDOS, campo: valor})) == 1


def test_limpiar():
    datos = usuarios.limpiar({**VALIDOS, "nombre": "  Ana  ", "correo": " ANA@Empresa.com ", "area": None})
    assert datos["nombre"] == "Ana"
    assert datos["correo"] == "ana@empresa.com"
    assert datos["area"] == ""
