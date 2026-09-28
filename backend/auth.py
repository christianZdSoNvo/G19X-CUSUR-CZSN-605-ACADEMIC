from backend import bitacora, db, errores, seguridad


def _parametros(cursor):
    cursor.execute(
        "SELECT clave, valor FROM Configuracion_sistema WHERE clave IN "
        "('max_intentos_login', 'minutos_bloqueo', 'minutos_inactividad_sesion')"
    )
    return {fila["clave"]: int(fila["valor"]) for fila in cursor.fetchall()}


def _intento_fallido(cursor, id_usuario, detalle):
    bitacora.registrar(cursor, id_usuario, "intento_fallido", "Usuarios", id_usuario, detalle)


def _validar_acceso(cursor, fila, usuario, contrasena, parametros):
    # Flujo de inicio de sesión del PRD, 12.3. Devuelve None o el código de error.
    if fila is None or not fila["activo"]:
        # Se calcula un hash igual para no revelar por el tiempo si el usuario existe
        seguridad.hashear(contrasena, "0" * 16)
        motivo = "usuario inexistente" if fila is None else "usuario inactivo"
        _intento_fallido(cursor, fila["id_usuario"] if fila else None,
                         {"usuario": usuario, "motivo": motivo})
        return "E-301"

    id_usuario = fila["id_usuario"]
    if fila["bloqueado"]:
        _intento_fallido(cursor, id_usuario, {"motivo": "cuenta bloqueada"})
        return "E-302"

    if not seguridad.verificar(contrasena, fila["salt"], fila["contrasena"]):
        intentos = fila["intentos_fallidos"] + 1
        if intentos >= parametros["max_intentos_login"]:
            cursor.execute(
                "UPDATE Usuarios SET intentos_fallidos = 0, "
                "bloqueado_hasta = NOW() + INTERVAL %s MINUTE WHERE id_usuario = %s",
                (parametros["minutos_bloqueo"], id_usuario),
            )
            _intento_fallido(cursor, id_usuario, {
                "motivo": "contraseña incorrecta", "intento": intentos,
                "bloqueo_minutos": parametros["minutos_bloqueo"],
            })
            return "E-302"
        cursor.execute("UPDATE Usuarios SET intentos_fallidos = %s WHERE id_usuario = %s",
                       (intentos, id_usuario))
        _intento_fallido(cursor, id_usuario, {"motivo": "contraseña incorrecta", "intento": intentos})
        return "E-301"

    cursor.execute(
        "UPDATE Usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id_usuario = %s",
        (id_usuario,),
    )
    bitacora.registrar(cursor, id_usuario, "inicio_sesion", "Usuarios", id_usuario)
    return None


def iniciar_sesion(usuario, contrasena):
    with db.transaccion() as cursor:
        parametros = _parametros(cursor)
        cursor.execute(
            "SELECT id_usuario, nombre, cargo, area, contrasena, salt, activo, intentos_fallidos, "
            "debe_cambiar_contrasena, bloqueado_hasta > NOW() AS bloqueado "
            "FROM Usuarios WHERE usuario = %s",
            (usuario,),
        )
        fila = cursor.fetchone()
        codigo = _validar_acceso(cursor, fila, usuario, contrasena, parametros)

    # Se lanza fuera de la transacción para que los intentos fallidos sí se guarden
    if codigo:
        raise errores.ErrorSistema(codigo)
    return {
        "id_usuario": fila["id_usuario"],
        "nombre": fila["nombre"],
        "cargo": fila["cargo"],
        "area": fila["area"],
        "debe_cambiar_contrasena": bool(fila["debe_cambiar_contrasena"]),
        "minutos_inactividad": parametros["minutos_inactividad_sesion"],
    }


def cambiar_contrasena(id_usuario, nueva, actual=None):
    # Devuelve la lista de problemas; vacía si se cambió.
    # "actual" solo se pide en el cambio voluntario, no en el obligatorio.
    problemas = seguridad.validar_politica(nueva)
    if problemas:
        return problemas

    with db.transaccion() as cursor:
        cursor.execute("SELECT contrasena, salt FROM Usuarios WHERE id_usuario = %s", (id_usuario,))
        fila = cursor.fetchone()
        if actual is not None and not seguridad.verificar(actual, fila["salt"], fila["contrasena"]):
            return ["La contraseña actual no es correcta."]
        if seguridad.verificar(nueva, fila["salt"], fila["contrasena"]):
            return ["La contraseña nueva debe ser distinta de la anterior."]

        salt = seguridad.generar_salt()
        cursor.execute(
            "UPDATE Usuarios SET contrasena = %s, salt = %s, fecha_cambio_contrasena = CURDATE(), "
            "debe_cambiar_contrasena = FALSE WHERE id_usuario = %s",
            (seguridad.hashear(nueva, salt), salt, id_usuario),
        )
        bitacora.registrar(cursor, id_usuario, "edicion", "Usuarios", id_usuario,
                           {"campo": "contrasena"})
    return []


def solicitar_restablecimiento(correo):
    # No devuelve nada: la pantalla muestra el mismo mensaje exista o no el correo
    with db.transaccion() as cursor:
        cursor.execute("SELECT usuario, nombre FROM Usuarios WHERE correo = %s AND activo", (correo,))
        solicitante = cursor.fetchone()
        if solicitante is None:
            return

        contenido = (f"{solicitante['nombre']} (usuario: {solicitante['usuario']}) solicitó "
                     f"restablecer su usuario o contraseña desde el inicio de sesión.")
        cursor.execute("SELECT id_usuario FROM Usuarios WHERE cargo = 'Administrador RH' AND activo")
        for administrador in cursor.fetchall():
            cursor.execute(
                "INSERT INTO Notificaciones (id_destinatario, contenido, tipo, grado_emergencia) "
                "VALUES (%s, %s, 'restablecer_acceso', 'medio')",
                (administrador["id_usuario"], contenido),
            )


def registrar_cierre(id_usuario, motivo):
    with db.transaccion() as cursor:
        bitacora.registrar(cursor, id_usuario, "cierre_sesion", "Usuarios", id_usuario,
                           {"motivo": motivo})
