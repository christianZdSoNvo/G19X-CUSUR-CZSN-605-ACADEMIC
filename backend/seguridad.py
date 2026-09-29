import hashlib
import secrets

# Mismo formato que el script SQL: SHA2(CONCAT(salt, contraseña), 256)
REQUISITOS = "Mínimo 8 caracteres, con al menos una mayúscula, una minúscula y un número."

# Sin caracteres que se confunden al dictarla en persona (0/O, 1/l/I)
_MAYUSCULAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_MINUSCULAS = "abcdefghijkmnpqrstuvwxyz"
_NUMEROS = "23456789"


def generar_salt():
    return secrets.token_hex(8)


def generar_temporal(longitud=10):
    # Contraseña temporal que cumple la política: una de cada tipo y el resto al azar
    todos = _MAYUSCULAS + _MINUSCULAS + _NUMEROS
    caracteres = [secrets.choice(_MAYUSCULAS), secrets.choice(_MINUSCULAS), secrets.choice(_NUMEROS)]
    caracteres += [secrets.choice(todos) for _ in range(longitud - 3)]
    secrets.SystemRandom().shuffle(caracteres)
    return "".join(caracteres)


def hashear(contrasena, salt):
    return hashlib.sha256((salt + contrasena).encode("utf-8")).hexdigest()


def verificar(contrasena, salt, hash_guardado):
    return secrets.compare_digest(hashear(contrasena, salt), hash_guardado)


def validar_politica(contrasena):
    problemas = []
    if len(contrasena) < 8:
        problemas.append("Debe tener al menos 8 caracteres.")
    if not any(c.isupper() for c in contrasena):
        problemas.append("Debe tener al menos una mayúscula.")
    if not any(c.islower() for c in contrasena):
        problemas.append("Debe tener al menos una minúscula.")
    if not any(c.isdigit() for c in contrasena):
        problemas.append("Debe tener al menos un número.")
    return problemas
