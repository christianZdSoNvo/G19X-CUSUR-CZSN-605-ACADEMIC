import re

from backend import bitacora, db, errores, permisos

# Manuales (PRD, 6.9, 9.4, 13.4 y 13.6). Ambos roles los consultan; solo el
# Administrador de RH los da de alta, edita y elimina. El Encargado solo ve los de
# las secciones que tiene en su menú.

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
MAX_IMAGEN = 5 * 1024 * 1024
MAX_ENLACE = 255
# Firmas de PNG y JPG: se revisa el contenido, no solo la extensión
_FIRMAS = {b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg"}


def secciones_permitidas(usuario):
    return [seccion for seccion, funcion in SECCIONES.items()
            if funcion is None or permisos.puede(usuario, funcion)]


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
        "seccion_software": str(datos.get("seccion_software") or "").strip(),
        "contenido_texto": str(datos.get("contenido_texto") or "").strip() or None,
        "contenido_enlace": str(datos.get("contenido_enlace") or "").strip() or None,
    }


def validar(datos, con_imagen):
    # Devuelve {campo: mensaje}; la imagen se valida aparte (E-402)
    problemas = {}
    if datos["seccion_software"] not in SECCIONES:
        problemas["seccion_software"] = "Seleccione una sección del sistema."
    enlace = datos["contenido_enlace"]
    if enlace and (len(enlace) > MAX_ENLACE or not re.fullmatch(r"https?://\S+", enlace)):
        problemas["contenido_enlace"] = f"El enlace debe empezar con http:// o https:// y tener hasta {MAX_ENLACE} caracteres."
    if not datos["contenido_texto"] and not enlace and not con_imagen:
        problemas["contenido_texto"] = "Escriba un texto o agregue una imagen o un enlace."
    return problemas


def listar(usuario, seccion=None, texto=""):
    # Manuales que el usuario puede ver, con filtro por sección y búsqueda en el texto
    permitidas = secciones_permitidas(usuario)
    if seccion:
        permitidas = [s for s in permitidas if s == seccion]
    if not permitidas:
        return []
    condiciones = [f"m.seccion_software IN ({', '.join(['%s'] * len(permitidas))})"]
    valores = list(permitidas)
    texto = texto.strip()
    if texto:
        condiciones.append("(m.contenido_texto LIKE %s OR m.seccion_software LIKE %s)")
        valores += [f"%{texto}%"] * 2
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT m.id_manual, m.seccion_software, m.contenido_texto, m.contenido_imagen, "
            "m.contenido_enlace, m.fecha_actualizacion, u.nombre AS edito "
            "FROM Manuales m JOIN Usuarios u ON u.id_usuario = m.id_usuario_edito "
            f"WHERE {' AND '.join(condiciones)} ORDER BY m.seccion_software, m.id_manual",
            valores,
        )
        manuales = cursor.fetchall()
    orden = list(SECCIONES)
    return sorted(manuales, key=lambda m: (orden.index(m["seccion_software"]), m["id_manual"]))


def hay_manuales(usuario):
    return bool(listar(usuario))


def _detalle(datos, imagen):
    # La imagen no va a la bitácora, solo si se agregó
    return {**datos, "contenido_texto": (datos["contenido_texto"] or "")[:200],
            "imagen": "sí" if imagen else "no"}


def crear(usuario, datos, imagen=None):
    # Devuelve (problemas, id_manual)
    permisos.exigir(usuario, "editar_manuales")
    datos = limpiar(datos)
    problemas = validar(datos, imagen is not None)
    if problemas:
        return problemas, None
    if imagen is not None:
        validar_imagen(imagen)
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Manuales (seccion_software, contenido_texto, contenido_imagen, contenido_enlace, "
            "id_usuario_edito) VALUES (%s, %s, %s, %s, %s)",
            (datos["seccion_software"], datos["contenido_texto"], imagen, datos["contenido_enlace"],
             usuario["id_usuario"]),
        )
        id_manual = cursor.lastrowid
        bitacora.registrar(cursor, usuario["id_usuario"], "alta", "Manuales", id_manual,
                           _detalle(datos, imagen is not None))
    return {}, id_manual


def editar(usuario, id_manual, datos, imagen=None, quitar_imagen=False):
    # imagen=None conserva la actual, salvo que se pida quitarla
    permisos.exigir(usuario, "editar_manuales")
    datos = limpiar(datos)
    with db.transaccion() as cursor:
        cursor.execute("SELECT contenido_imagen IS NOT NULL AS tiene_imagen FROM Manuales "
                       "WHERE id_manual = %s", (id_manual,))
        fila = cursor.fetchone()
    if fila is None:
        raise errores.ErrorSistema("E-003")
    con_imagen = imagen is not None or (fila["tiene_imagen"] and not quitar_imagen)
    problemas = validar(datos, con_imagen)
    if problemas:
        return problemas
    if imagen is not None:
        validar_imagen(imagen)

    columnas = ["seccion_software = %s", "contenido_texto = %s", "contenido_enlace = %s",
                "id_usuario_edito = %s", "fecha_actualizacion = NOW()"]
    valores = [datos["seccion_software"], datos["contenido_texto"], datos["contenido_enlace"],
               usuario["id_usuario"]]
    if imagen is not None or quitar_imagen:
        columnas.append("contenido_imagen = %s")
        valores.append(imagen)
    with db.transaccion() as cursor:
        cursor.execute(f"UPDATE Manuales SET {', '.join(columnas)} WHERE id_manual = %s",
                       (*valores, id_manual))
        bitacora.registrar(cursor, usuario["id_usuario"], "edicion", "Manuales", id_manual,
                           _detalle(datos, con_imagen))
    return {}


def eliminar(usuario, id_manual):
    permisos.exigir(usuario, "editar_manuales")
    with db.transaccion() as cursor:
        cursor.execute("SELECT seccion_software FROM Manuales WHERE id_manual = %s", (id_manual,))
        fila = cursor.fetchone()
        if fila is None:
            raise errores.ErrorSistema("E-003")
        cursor.execute("DELETE FROM Manuales WHERE id_manual = %s", (id_manual,))
        bitacora.registrar(cursor, usuario["id_usuario"], "eliminacion", "Manuales", id_manual,
                           {"seccion_software": fila["seccion_software"]})
