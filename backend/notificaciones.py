from backend import bitacora, db, errores, permisos, talentos

# Notificaciones y bandeja (PRD, 6.6, 9.5, 12.3 y 13.7). El Administrador envía a
# cualquier usuario; el Encargado solo a los Administradores y sobre talentos de su
# área. Quien recibe la notificación la marca como revisada, con respuesta opcional.

TIPOS = {
    "correccion_datos": "Corrección de datos",
    "reevaluacion": "Reevaluación con IA",
    "alerta_automatica": "Alerta automática",
    "restablecer_acceso": "Restablecer acceso",
    "error_sistema": "Error del sistema",
    "otro": "Otro",
}
# Tipos que se eligen al enviar una notificación manual
TIPOS_MANUALES = ("correccion_datos", "reevaluacion", "error_sistema", "otro")
# Tipos que siempre se refieren a un talento
CON_TALENTO = ("correccion_datos", "reevaluacion")
GRADOS = ("bajo", "medio", "alto")
ESTADOS = ("pendiente", "revisado")
MAX_TEXTO = 1000
MAX_RESPUESTA = 500
SIN_EMISOR = {"alerta_automatica": "Sistema", "restablecer_acceso": "Solicitud desde inicio de sesión"}

_CONSULTA = (
    "SELECT n.id_noti, n.fecha_creacion, n.id_emisor, n.id_destinatario, n.contenido, n.estado, n.tipo, "
    "n.id_talento, n.respuesta, n.fecha_revision, n.grado_emergencia, "
    "d.nombre AS destinatario, e.nombre AS emisor, t.nombre AS talento, t.area AS area_talento "
    "FROM Notificaciones n JOIN Usuarios d ON d.id_usuario = n.id_destinatario "
    "LEFT JOIN Usuarios e ON e.id_usuario = n.id_emisor "
    "LEFT JOIN Talentos t ON t.id_talento = n.id_talento "
)


def nombre_emisor(notificacion):
    if notificacion["emisor"]:
        return notificacion["emisor"]
    return SIN_EMISOR.get(notificacion["tipo"], "Sistema")


def texto(notificacion):
    # Criterio de la notificación (PRD, 6.6): destinatario y grado en la primera línea,
    # el texto en el siguiente párrafo y el emisor al final
    return (f"{notificacion['destinatario']} [IMPORTANCIA: {notificacion['grado_emergencia'].upper()}]\n\n"
            f"{notificacion['contenido']}\n\n"
            f"Emisor: {nombre_emisor(notificacion)}")


def destinatarios(usuario):
    # Usuarios activos a los que puede escribir: el Encargado solo a los Administradores
    condicion = "" if permisos.es_administrador(usuario) else " AND cargo = %s"
    parametros = () if permisos.es_administrador(usuario) else (permisos.ADMINISTRADOR,)
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_usuario, nombre, cargo, area FROM Usuarios WHERE activo AND id_usuario <> %s"
            + condicion + " ORDER BY cargo, nombre",
            (usuario["id_usuario"], *parametros),
        )
        return cursor.fetchall()


def validar(usuario, datos):
    # Devuelve {campo: mensaje}
    problemas = {}
    if datos.get("tipo") not in TIPOS_MANUALES:
        problemas["tipo"] = "Seleccione el tipo de notificación."
    if datos.get("grado_emergencia") not in GRADOS:
        problemas["grado_emergencia"] = "Seleccione el grado de emergencia."
    contenido = (datos.get("contenido") or "").strip()
    if not contenido or len(contenido) > MAX_TEXTO:
        problemas["contenido"] = f"Escriba el texto de la notificación (hasta {MAX_TEXTO} caracteres)."
    if datos.get("tipo") in CON_TALENTO and not datos.get("id_talento"):
        problemas["id_talento"] = "Seleccione el talento al que se refiere la solicitud."
    if datos.get("id_destinatario") not in {d["id_usuario"] for d in destinatarios(usuario)}:
        problemas["id_destinatario"] = "Seleccione un destinatario válido."
    return problemas


def enviar(usuario, datos):
    # Devuelve ({campo: mensaje}, id de la notificación). Si falla la BD lanza
    # ErrorSistema y la página ofrece el borrador para guardarlo fuera del sistema.
    permisos.exigir(usuario, "notificaciones")
    datos = {**datos, "contenido": (datos.get("contenido") or "").strip()}
    problemas = validar(usuario, datos)
    if problemas:
        return problemas, None
    if datos.get("id_talento"):
        # El Encargado solo puede referirse a talentos de su área (E-304 si no)
        talento = talentos.obtener(usuario, datos["id_talento"])
        if talento is None:
            return {"id_talento": talentos.NO_IDENTIFICADO}, None
        # Un Encargado tampoco puede recibir datos de talentos de otra área
        destinatario = next(d for d in destinatarios(usuario) if d["id_usuario"] == datos["id_destinatario"])
        if destinatario["cargo"] == permisos.ENCARGADO and destinatario["area"] != talento["area"]:
            return {"id_talento": f"El talento no pertenece al área del destinatario ({destinatario['area']})."}, None
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Notificaciones (id_emisor, id_destinatario, contenido, tipo, id_talento, grado_emergencia) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (usuario["id_usuario"], datos["id_destinatario"], datos["contenido"], datos["tipo"],
             datos.get("id_talento"), datos["grado_emergencia"]),
        )
        id_noti = cursor.lastrowid
        bitacora.registrar(cursor, usuario["id_usuario"], "alta", "Notificaciones", id_noti,
                           {"tipo": datos["tipo"], "id_destinatario": datos["id_destinatario"],
                            "id_talento": datos.get("id_talento")})
    return {}, id_noti


def borrador(usuario, datos, nombre_destinatario):
    # Texto para guardar fuera del sistema cuando no hay conexión (flujo alterno, PRD 6.6)
    return texto({"destinatario": nombre_destinatario, "grado_emergencia": datos.get("grado_emergencia") or "bajo",
                  "contenido": (datos.get("contenido") or "").strip(), "emisor": usuario["nombre"],
                  "tipo": datos.get("tipo")})


def recibidas(usuario, estado=None, grados=()):
    return _listar(usuario, "n.id_destinatario = %s", estado, grados)


def enviadas(usuario, estado=None, grados=()):
    return _listar(usuario, "n.id_emisor = %s", estado, grados)


def _listar(usuario, condicion, estado, grados):
    permisos.exigir(usuario, "notificaciones")
    condiciones, parametros = [condicion], [usuario["id_usuario"]]
    if estado:
        condiciones.append("n.estado = %s")
        parametros.append(estado)
    if grados:
        condiciones.append("n.grado_emergencia IN (" + ", ".join(["%s"] * len(grados)) + ")")
        parametros.extend(grados)
    with db.transaccion() as cursor:
        cursor.execute(_CONSULTA + "WHERE " + " AND ".join(condiciones)
                       + " ORDER BY n.estado = 'revisado', n.fecha_creacion DESC, n.id_noti DESC",
                       tuple(parametros))
        return cursor.fetchall()


def pendientes(usuario):
    # Contador del menú (PRD, 12.3)
    with db.transaccion() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM Notificaciones WHERE id_destinatario = %s "
                       "AND estado = 'pendiente'", (usuario["id_usuario"],))
        return cursor.fetchone()["total"]


def marcar_revisada(usuario, id_noti, respuesta=""):
    # Solo el destinatario la marca; la respuesta es opcional
    permisos.exigir(usuario, "notificaciones")
    respuesta = (respuesta or "").strip()
    if len(respuesta) > MAX_RESPUESTA:
        return f"La respuesta admite hasta {MAX_RESPUESTA} caracteres."
    with db.transaccion() as cursor:
        cursor.execute(
            "UPDATE Notificaciones SET estado = 'revisado', fecha_revision = NOW(), respuesta = %s "
            "WHERE id_noti = %s AND id_destinatario = %s AND estado = 'pendiente'",
            (respuesta or None, id_noti, usuario["id_usuario"]),
        )
        if cursor.rowcount != 1:
            raise errores.ErrorSistema("E-003")
        bitacora.registrar(cursor, usuario["id_usuario"], "edicion", "Notificaciones", id_noti,
                           {"estado": "revisado", "respuesta": respuesta or None})
    return None
