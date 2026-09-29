import re

from backend import bitacora, catalogos, db, permisos, seguridad

# Gestión de usuarios (PRD, 6.7 y 13.4). Solo la usa el Administrador de RH;
# "administrador" es el usuario de la sesión y queda como autor en la bitácora.

CARGOS = [permisos.ADMINISTRADOR, permisos.ENCARGADO]
CAMPOS = ("nombre", "usuario", "correo", "tel_mx", "cargo", "area")


def validar(datos):
    problemas = []
    if not datos["nombre"] or len(datos["nombre"]) > 50:
        problemas.append("El nombre es obligatorio y admite hasta 50 caracteres.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,30}", datos["usuario"]):
        problemas.append("El usuario debe tener de 3 a 30 caracteres: letras sin acentos, "
                         "números, punto, guion o guion bajo.")
    if len(datos["correo"]) > 70 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", datos["correo"]):
        problemas.append("Escriba un correo válido de hasta 70 caracteres.")
    if not re.fullmatch(r"[0-9]{10}", datos["tel_mx"]):
        problemas.append("El teléfono debe tener 10 dígitos.")
    if datos["cargo"] not in CARGOS:
        problemas.append("Seleccione un cargo válido.")
    if datos["area"] not in catalogos.AREAS:
        problemas.append("Seleccione un área válida.")
    return problemas


def limpiar(datos):
    limpio = {campo: str(datos.get(campo) or "").strip() for campo in CAMPOS}
    limpio["correo"] = limpio["correo"].lower()
    return limpio


def listar():
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_usuario, nombre, usuario, correo, tel_mx, cargo, area, activo, "
            "debe_cambiar_contrasena, bloqueado_hasta > NOW() AS bloqueado "
            "FROM Usuarios ORDER BY activo DESC, nombre"
        )
        return cursor.fetchall()


def crear(administrador, datos):
    # Devuelve (problemas, contraseña temporal); la contraseña solo se muestra una vez
    datos = limpiar(datos)
    problemas = validar(datos)
    if problemas:
        return problemas, None

    temporal = seguridad.generar_temporal()
    salt = seguridad.generar_salt()
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Usuarios (cargo, area, nombre, usuario, correo, contrasena, salt, "
            "fecha_cambio_contrasena, debe_cambiar_contrasena, tel_mx) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, CURDATE(), TRUE, %s)",
            (datos["cargo"], datos["area"], datos["nombre"], datos["usuario"], datos["correo"],
             seguridad.hashear(temporal, salt), salt, datos["tel_mx"]),
        )
        id_nuevo = cursor.lastrowid
        bitacora.registrar(cursor, administrador["id_usuario"], "alta", "Usuarios", id_nuevo,
                           {"usuario": datos["usuario"], "cargo": datos["cargo"], "area": datos["area"]})
    return [], temporal


def editar(administrador, id_usuario, datos):
    datos = limpiar(datos)
    problemas = validar(datos)
    if problemas:
        return problemas

    with db.transaccion() as cursor:
        actual = _bloquear_fila(cursor, id_usuario)
        if actual["cargo"] == permisos.ADMINISTRADOR and datos["cargo"] != permisos.ADMINISTRADOR:
            if id_usuario == administrador["id_usuario"]:
                return ["No puede quitarse a sí mismo el cargo de Administrador."]
            if actual["activo"] and _administradores_activos(cursor) <= 1:
                return ["Debe quedar al menos un Administrador de RH activo."]

        cambios = {campo: datos[campo] for campo in CAMPOS if datos[campo] != actual[campo]}
        if not cambios:
            return []
        cursor.execute(
            "UPDATE Usuarios SET " + ", ".join(f"{campo} = %s" for campo in cambios)
            + " WHERE id_usuario = %s",
            (*cambios.values(), id_usuario),
        )
        bitacora.registrar(cursor, administrador["id_usuario"], "edicion", "Usuarios", id_usuario,
                           {"campos": list(cambios)})
    return []


def cambiar_estado(administrador, id_usuario, activo):
    # Desactivar es una baja lógica: el usuario ya no puede iniciar sesión
    with db.transaccion() as cursor:
        actual = _bloquear_fila(cursor, id_usuario)
        if not activo:
            if id_usuario == administrador["id_usuario"]:
                return ["No puede desactivar su propia cuenta."]
            if actual["cargo"] == permisos.ADMINISTRADOR and _administradores_activos(cursor) <= 1:
                return ["Debe quedar al menos un Administrador de RH activo."]
        if bool(actual["activo"]) == activo:
            return []
        cursor.execute("UPDATE Usuarios SET activo = %s WHERE id_usuario = %s", (activo, id_usuario))
        bitacora.registrar(cursor, administrador["id_usuario"], "edicion" if activo else "baja",
                           "Usuarios", id_usuario, {"activo": activo})
    return []


def restablecer_contrasena(administrador, id_usuario, origen="Gestión de usuarios"):
    # Contraseña temporal que el Administrador comunica en persona (PRD, 6.7).
    # También desbloquea la cuenta para que el usuario pueda entrar de inmediato.
    temporal = seguridad.generar_temporal()
    salt = seguridad.generar_salt()
    with db.transaccion() as cursor:
        _bloquear_fila(cursor, id_usuario)
        cursor.execute(
            "UPDATE Usuarios SET contrasena = %s, salt = %s, fecha_cambio_contrasena = CURDATE(), "
            "debe_cambiar_contrasena = TRUE, intentos_fallidos = 0, bloqueado_hasta = NULL "
            "WHERE id_usuario = %s",
            (seguridad.hashear(temporal, salt), salt, id_usuario),
        )
        bitacora.registrar(cursor, administrador["id_usuario"], "edicion", "Usuarios", id_usuario,
                           {"campo": "contrasena", "motivo": "restablecimiento", "origen": origen})
    return temporal


def solicitudes_pendientes(administrador):
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_noti, fecha_creacion, contenido FROM Notificaciones "
            "WHERE id_destinatario = %s AND tipo = 'restablecer_acceso' AND estado = 'pendiente' "
            "ORDER BY fecha_creacion",
            (administrador["id_usuario"],),
        )
        return cursor.fetchall()


def marcar_solicitud_revisada(administrador, id_noti, respuesta):
    with db.transaccion() as cursor:
        cursor.execute(
            "UPDATE Notificaciones SET estado = 'revisado', fecha_revision = NOW(), respuesta = %s "
            "WHERE id_noti = %s AND id_destinatario = %s",
            (respuesta.strip() or None, id_noti, administrador["id_usuario"]),
        )


def _bloquear_fila(cursor, id_usuario):
    # FOR UPDATE evita que dos cambios simultáneos dejen al sistema sin Administrador
    cursor.execute(
        "SELECT " + ", ".join(CAMPOS) + ", activo FROM Usuarios WHERE id_usuario = %s FOR UPDATE",
        (id_usuario,),
    )
    return cursor.fetchone()


def _administradores_activos(cursor):
    cursor.execute(
        "SELECT COUNT(*) AS total FROM Usuarios WHERE cargo = %s AND activo FOR UPDATE",
        (permisos.ADMINISTRADOR,),
    )
    return cursor.fetchone()["total"]
