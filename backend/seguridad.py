import base64
import hashlib
import secrets

# Contraseñas con PBKDF2-SHA256; se guardan como "pbkdf2_sha256$<iteraciones>$<hash base64>"
ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 600_000

# Valor de "contrasena" del Administrador inicial que crea crear_bd.sql:
# no coincide con ninguna contraseña hasta que reset_admin.py le asigna una
PENDIENTE = "pendiente"

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


def _pbkdf2(contrasena, salt, iteraciones):
    # El hash va en base64 (44 caracteres) para que todo quepa en Usuarios.contrasena VARCHAR(70)
    clave = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), salt.encode("utf-8"), iteraciones)
    return f"{ALGORITMO}${iteraciones}${base64.b64encode(clave).decode('ascii')}"


def _sha256_anterior(contrasena, salt):
    # Formato anterior: SHA2(CONCAT(salt, contraseña), 256). Solo se usa para verificar
    # contraseñas guardadas antes del cambio; se reemplazan al iniciar sesión.
    return hashlib.sha256((salt + contrasena).encode("utf-8")).hexdigest()


def hashear(contrasena, salt):
    return _pbkdf2(contrasena, salt, ITERACIONES)


def verificar(contrasena, salt, hash_guardado):
    partes = hash_guardado.split("$")
    if len(partes) == 3 and partes[0] == ALGORITMO and partes[1].isdigit():
        calculado = _pbkdf2(contrasena, salt, int(partes[1]))
    elif len(hash_guardado) == 64:
        calculado = _sha256_anterior(contrasena, salt)
    else:
        # PENDIENTE o cualquier valor desconocido: nunca coincide
        return False
    return secrets.compare_digest(calculado, hash_guardado)


def necesita_actualizar(hash_guardado):
    # True si está en el formato anterior o con otro número de iteraciones
    return hash_guardado != PENDIENTE and not hash_guardado.startswith(f"{ALGORITMO}${ITERACIONES}$")


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
