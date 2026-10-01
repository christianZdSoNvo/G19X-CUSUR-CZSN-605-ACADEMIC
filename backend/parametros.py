import re

from backend import bitacora, db, permisos

# Parámetros del sistema (PRD, 9.9 y 13.4). Los módulos que los usan los leen de
# Configuracion_sistema en cada operación, así que un cambio se aplica de inmediato:
# login y bloqueo en el siguiente intento, la IA en la siguiente evaluación y la
# variación de alertas en la siguiente alerta. La inactividad se toma al iniciar
# sesión (la sesión del Administrador que la cambia se actualiza al guardar).

POR_DEFINIR = "Por definir"

# clave -> (grupo, etiqueta, tipo, mínimo, máximo); en los de texto, el máximo es la longitud
PARAMETROS = {
    "nombre_soporte": ("Contacto de soporte", "Nombre", "texto", 1, 100),
    "correo_soporte": ("Contacto de soporte", "Correo", "correo", 1, 70),
    "telefono_soporte": ("Contacto de soporte", "Teléfono (10 dígitos)", "telefono", 10, 10),
    "tiempo_max_ia_seg": ("Inteligencia artificial", "Tiempo máximo de respuesta (segundos)", "entero", 30, 600),
    "intentos_ia_por_dia": ("Inteligencia artificial", "Evaluaciones por talento al día", "entero", 1, 10),
    "variacion_alerta_default": ("Alertas", "Variación por defecto (puntos)", "entero", 1, 100),
    "max_intentos_login": ("Contraseñas y sesión", "Intentos fallidos antes del bloqueo", "entero", 3, 10),
    "minutos_bloqueo": ("Contraseñas y sesión", "Minutos de bloqueo", "entero", 1, 1440),
    "minutos_inactividad_sesion": ("Contraseñas y sesión", "Minutos de inactividad antes de cerrar la sesión",
                                   "entero", 5, 480),
}
GRUPOS = tuple(dict.fromkeys(grupo for grupo, *_ in PARAMETROS.values()))
SOPORTE = ("nombre_soporte", "correo_soporte", "telefono_soporte")


def obtener(claves=None):
    # {clave: valor} como texto; los enteros se convierten con int() donde se usan
    claves = tuple(claves or PARAMETROS)
    with db.transaccion() as cursor:
        cursor.execute(
            f"SELECT clave, valor FROM Configuracion_sistema WHERE clave IN ({', '.join(['%s'] * len(claves))})",
            claves,
        )
        return {fila["clave"]: fila["valor"] for fila in cursor.fetchall()}


def listar():
    # Para la pantalla: valor, descripción y quién lo modificó por última vez
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT c.clave, c.valor, c.descripcion, c.fecha_modificacion, u.nombre AS modifico "
            "FROM Configuracion_sistema c LEFT JOIN Usuarios u ON u.id_usuario = c.id_usuario_modifico"
        )
        return {fila["clave"]: fila for fila in cursor.fetchall() if fila["clave"] in PARAMETROS}


def contacto_soporte():
    # Nombre, correo y teléfono de soporte; sin definir quedan como "Por definir"
    valores = obtener(SOPORTE)
    return {clave.removesuffix("_soporte"): valores.get(clave) or POR_DEFINIR for clave in SOPORTE}


def definido(valor):
    return bool(valor) and valor != POR_DEFINIR


def limpiar(valores):
    # Un dato de soporte vacío vuelve a quedar "Por definir"
    limpio = {clave: str(valor if valor is not None else "").strip() for clave, valor in valores.items()
              if clave in PARAMETROS}
    for clave in SOPORTE:
        if clave in limpio and not limpio[clave]:
            limpio[clave] = POR_DEFINIR
    return limpio


def validar(valores):
    # Devuelve {clave: mensaje}; "Por definir" se acepta en el contacto de soporte
    problemas = {}
    for clave, valor in valores.items():
        _, _, tipo, minimo, maximo = PARAMETROS[clave]
        if tipo == "entero":
            if not re.fullmatch(r"[0-9]+", valor) or not minimo <= int(valor) <= maximo:
                problemas[clave] = f"Escriba un número entero de {minimo} a {maximo}."
        elif valor == POR_DEFINIR:
            continue
        elif tipo == "texto" and not minimo <= len(valor) <= maximo:
            problemas[clave] = f"Es obligatorio y admite hasta {maximo} caracteres."
        elif tipo == "correo" and (len(valor) > maximo
                                   or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor)):
            problemas[clave] = f"Escriba un correo válido de hasta {maximo} caracteres."
        elif tipo == "telefono" and not re.fullmatch(r"[0-9]{10}", valor):
            problemas[clave] = "El teléfono debe tener 10 dígitos."
    return problemas


def guardar(usuario, valores):
    # Guarda solo los valores que cambiaron; una fila de bitácora "configuracion" por
    # parámetro con el valor anterior y el nuevo. Devuelve (problemas, claves cambiadas).
    permisos.exigir(usuario, "parametros")
    valores = limpiar(valores)
    problemas = validar(valores)
    if problemas:
        return problemas, []

    cambiados = []
    with db.transaccion() as cursor:
        cursor.execute("SELECT id_config, clave, valor FROM Configuracion_sistema FOR UPDATE")
        actuales = {fila["clave"]: fila for fila in cursor.fetchall()}
        for clave, nuevo in valores.items():
            actual = actuales.get(clave)
            if actual is None:
                cursor.execute(
                    "INSERT INTO Configuracion_sistema (clave, valor, id_usuario_modifico) VALUES (%s, %s, %s)",
                    (clave, nuevo, usuario["id_usuario"]),
                )
                id_config, anterior = cursor.lastrowid, None
            elif actual["valor"] == nuevo:
                continue
            else:
                cursor.execute(
                    "UPDATE Configuracion_sistema SET valor = %s, id_usuario_modifico = %s, "
                    "fecha_modificacion = NOW() WHERE id_config = %s",
                    (nuevo, usuario["id_usuario"], actual["id_config"]),
                )
                id_config, anterior = actual["id_config"], actual["valor"]
            bitacora.registrar(cursor, usuario["id_usuario"], "configuracion", "Configuracion_sistema",
                               id_config, {"clave": clave, "anterior": anterior, "nuevo": nuevo})
            cambiados.append(clave)
    return {}, cambiados
