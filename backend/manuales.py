import re

from backend import bitacora, db, errores, permisos

# Manuales (PRD, 6.9, 9.4, 13.4 y 13.6). Ambos roles los consultan; solo el
# Administrador de RH los da de alta, edita y elimina. Cada manual está dirigido a un
# cargo (columna dirigido_a, con los mismos valores que Usuarios.cargo): cada usuario
# consulta los de su cargo, y los del Encargado solo pueden ser de las secciones que
# tiene en su menú. El Administrador también puede consultar los del Encargado.

# Sección del software -> función de la matriz de permisos (None = todos los usuarios)
SECCIONES = {
    "Inicio de sesión": None,
    "Talentos": "ver_talentos",
    "Paneles analíticos": "paneles",
    "Reportes": "reportes",
    "Historial y evolución": "historial",
    "Notificaciones": "notificaciones",
    "Configuración": "configuracion_general",
    "Gestión de usuarios": "gestion_usuarios",
    "Parámetros del sistema": "parametros",
    "Bitácora": "bitacora",
    "Soporte": "soporte",
}
CARGOS = (permisos.ADMINISTRADOR, permisos.ENCARGADO)
MAX_IMAGEN_MB = 5   # también es el límite que muestran los cargadores de archivos
MAX_IMAGEN = MAX_IMAGEN_MB * 1024 * 1024
MAX_IMAGENES = 10   # por manual
MAX_ENLACE = 255
# Firmas de PNG y JPG: se revisa el contenido, no solo la extensión
_FIRMAS = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg"}


def secciones_de(cargo):
    # Secciones del menú de ese cargo
    return [seccion for seccion, funcion in SECCIONES.items()
            if funcion is None or cargo in permisos.MATRIZ[funcion]]


def secciones_permitidas(usuario):
    return secciones_de(usuario["cargo"])


def _cargo_consultado(usuario, dirigido_a):
    # None = los de su propio cargo; solo el Administrador consulta los de otro cargo
    if dirigido_a is None or dirigido_a == usuario["cargo"]:
        return usuario["cargo"]
    permisos.exigir(usuario, "editar_manuales")
    if dirigido_a not in CARGOS:
        raise errores.ErrorSistema("E-003")
    return dirigido_a


def tipo_imagen(contenido):
    for firma, tipo in _FIRMAS.items():
        if contenido.startswith(firma):
            return tipo
    return None


def validar_imagen(contenido):
    # E-402 si no es PNG/JPG o pasa de 5 MB (PRD, 7)
    if len(contenido) > MAX_IMAGEN or tipo_imagen(contenido) is None:
        raise errores.ErrorSistema("E-402")


def limpiar(datos):
    return {
        "dirigido_a": datos.get("dirigido_a"),
        "seccion_software": str(datos.get("seccion_software") or "").strip(),
        "contenido_texto": str(datos.get("contenido_texto") or "").strip() or None,
        "contenido_enlace": str(datos.get("contenido_enlace") or "").strip() or None,
    }


def validar(datos, con_imagen):
    # Devuelve {campo: mensaje}; las imágenes se validan aparte (E-402 y cantidad máxima)
    problemas = {}
    if datos["dirigido_a"] not in CARGOS:
        problemas["dirigido_a"] = "Seleccione a quién va dirigido el manual."
    if datos["seccion_software"] not in SECCIONES:
        problemas["seccion_software"] = "Seleccione una sección del sistema."
    elif datos["dirigido_a"] in CARGOS and datos["seccion_software"] not in secciones_de(datos["dirigido_a"]):
        problemas["seccion_software"] = (f"La sección no está en el menú del "
                                         f"{permisos.NOMBRES_CARGO[datos['dirigido_a']]}.")
    enlace = datos["contenido_enlace"]
    if enlace and (len(enlace) > MAX_ENLACE or not re.fullmatch(r"https?://\S+", enlace)):
        problemas["contenido_enlace"] = f"El enlace debe empezar con http:// o https:// y tener hasta {MAX_ENLACE} caracteres."
    if not datos["contenido_texto"] and not enlace and not con_imagen:
        problemas["contenido_texto"] = "Escriba un texto o agregue una imagen o un enlace."
    return problemas


def listar(usuario, seccion=None, texto="", dirigido_a=None):
    # Manuales dirigidos a un cargo (por omisión, el del usuario), con filtro por sección
    # y búsqueda en el texto; cada uno trae sus imágenes en orden
    # ("imagenes": [{"id_imagen", "imagen"}])
    cargo = _cargo_consultado(usuario, dirigido_a)
    permitidas = secciones_de(cargo)
    if seccion:
        permitidas = [s for s in permitidas if s == seccion]
    if not permitidas:
        return []
    condiciones = ["m.dirigido_a = %s", f"m.seccion_software IN ({', '.join(['%s'] * len(permitidas))})"]
    valores = [cargo, *permitidas]
    texto = texto.strip()
    if texto:
        condiciones.append("(m.contenido_texto LIKE %s OR m.seccion_software LIKE %s)")
        valores += [f"%{texto}%"] * 2
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT m.id_manual, m.dirigido_a, m.seccion_software, m.contenido_texto, m.contenido_enlace, "
            "m.fecha_actualizacion, u.nombre AS edito "
            "FROM Manuales m JOIN Usuarios u ON u.id_usuario = m.id_usuario_edito "
            f"WHERE {' AND '.join(condiciones)} ORDER BY m.seccion_software, m.id_manual",
            valores,
        )
        manuales = cursor.fetchall()
        imagenes = {}
        if manuales:
            ids = [m["id_manual"] for m in manuales]
            cursor.execute(
                "SELECT id_imagen, id_manual, imagen FROM Manual_imagenes "
                f"WHERE id_manual IN ({', '.join(['%s'] * len(ids))}) ORDER BY id_manual, orden, id_imagen",
                ids,
            )
            for fila in cursor.fetchall():
                imagenes.setdefault(fila["id_manual"], []).append(
                    {"id_imagen": fila["id_imagen"], "imagen": fila["imagen"]})
    for manual in manuales:
        manual["imagenes"] = imagenes.get(manual["id_manual"], [])
    orden = list(SECCIONES)
    return sorted(manuales, key=lambda m: (orden.index(m["seccion_software"]), m["id_manual"]))


def hay_manuales(usuario, dirigido_a=None):
    return bool(listar(usuario, dirigido_a=dirigido_a))


def _detalle(datos, imagenes):
    # Las imágenes no van a la bitácora, solo cuántas tiene el manual
    return {**datos, "contenido_texto": (datos["contenido_texto"] or "")[:200], "imagenes": imagenes}


def _validar_imagenes(nuevas, total):
    # Cada imagen: PNG/JPG de hasta 5 MB (E-402); en total, hasta MAX_IMAGENES por manual
    for imagen in nuevas:
        validar_imagen(imagen)
    if total > MAX_IMAGENES:
        return {"imagenes": f"Un manual puede tener hasta {MAX_IMAGENES} imágenes."}
    return {}


def _agregar_imagenes(cursor, id_manual, nuevas):
    # Las imágenes nuevas van al final, en el orden en que se eligieron
    cursor.execute("SELECT COALESCE(MAX(orden), 0) AS ultimo FROM Manual_imagenes WHERE id_manual = %s",
                   (id_manual,))
    ultimo = cursor.fetchone()["ultimo"]
    for posicion, imagen in enumerate(nuevas, start=ultimo + 1):
        cursor.execute("INSERT INTO Manual_imagenes (id_manual, orden, imagen) VALUES (%s, %s, %s)",
                       (id_manual, posicion, imagen))


def crear(usuario, datos, imagenes=()):
    # Devuelve (problemas, id_manual)
    permisos.exigir(usuario, "editar_manuales")
    datos = limpiar(datos)
    imagenes = list(imagenes)
    problemas = validar(datos, bool(imagenes))
    if problemas:
        return problemas, None
    problemas = _validar_imagenes(imagenes, len(imagenes))
    if problemas:
        return problemas, None
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Manuales (dirigido_a, seccion_software, contenido_texto, contenido_enlace, "
            "id_usuario_edito) VALUES (%s, %s, %s, %s, %s)",
            (datos["dirigido_a"], datos["seccion_software"], datos["contenido_texto"], datos["contenido_enlace"], usuario["id_usuario"]),
        )
        id_manual = cursor.lastrowid
        _agregar_imagenes(cursor, id_manual, imagenes)
        bitacora.registrar(cursor, usuario["id_usuario"], "alta", "Manuales", id_manual,
                           _detalle(datos, len(imagenes)))
    return {}, id_manual


def editar(usuario, id_manual, datos, nuevas=(), quitar=()):
    # nuevas: imágenes que se agregan al final; quitar: id_imagen de las que se eliminan.
    # Las demás imágenes se conservan. El cargo al que va dirigido no cambia.
    permisos.exigir(usuario, "editar_manuales")
    nuevas, quitar = list(nuevas), set(quitar)
    with db.transaccion() as cursor:
        cursor.execute("SELECT dirigido_a FROM Manuales WHERE id_manual = %s", (id_manual,))
        fila = cursor.fetchone()
        if fila is None:
            raise errores.ErrorSistema("E-003")
        datos = limpiar({**datos, "dirigido_a": fila["dirigido_a"]})
        cursor.execute("SELECT id_imagen FROM Manual_imagenes WHERE id_manual = %s", (id_manual,))
        actuales = {fila["id_imagen"] for fila in cursor.fetchall()}
    quitar &= actuales
    total = len(actuales) - len(quitar) + len(nuevas)
    problemas = validar(datos, total > 0)
    if problemas:
        return problemas
    problemas = _validar_imagenes(nuevas, total)
    if problemas:
        return problemas

    with db.transaccion() as cursor:
        cursor.execute(
            "UPDATE Manuales SET seccion_software = %s, contenido_texto = %s, contenido_enlace = %s, "
            "id_usuario_edito = %s, fecha_actualizacion = NOW() WHERE id_manual = %s",
            (datos["seccion_software"], datos["contenido_texto"], datos["contenido_enlace"],
             usuario["id_usuario"], id_manual),
        )
        if quitar:
            cursor.execute(f"DELETE FROM Manual_imagenes WHERE id_imagen IN ({', '.join(['%s'] * len(quitar))})",
                           list(quitar))
        _agregar_imagenes(cursor, id_manual, nuevas)
        bitacora.registrar(cursor, usuario["id_usuario"], "edicion", "Manuales", id_manual,
                           _detalle(datos, total))
    return {}


def eliminar(usuario, id_manual):
    # Sus imágenes se borran con él (ON DELETE CASCADE)
    permisos.exigir(usuario, "editar_manuales")
    with db.transaccion() as cursor:
        cursor.execute("SELECT dirigido_a, seccion_software FROM Manuales WHERE id_manual = %s", (id_manual,))
        fila = cursor.fetchone()
        if fila is None:
            raise errores.ErrorSistema("E-003")
        cursor.execute("DELETE FROM Manuales WHERE id_manual = %s", (id_manual,))
        bitacora.registrar(cursor, usuario["id_usuario"], "eliminacion", "Manuales", id_manual,
                           {"dirigido_a": fila["dirigido_a"], "seccion_software": fila["seccion_software"]})
