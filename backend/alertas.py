import datetime

from backend import bitacora, catalogos, db, errores, ia, permisos

# Alertas automáticas (PRD, 6.6, 9.8 y 12.3). Las reglas de variación se revisan al
# guardar una evaluación o la edición de un talento, dentro de la misma transacción;
# la de "días sin evaluar" se revisa al iniciar sesión. Cada regla que se cumple crea
# una notificación "alerta_automatica" sin emisor para su destinatario.

INDICADORES = {
    "puntuacion_ia": "Puntuación de IA",
    "nivel_potencial": "Nivel de potencial",
    "desempeno_previo": "Desempeño previo",
    "sin_evaluacion": "Días sin evaluar",
}
CONDICIONES = {
    "disminuye": "Disminuye",
    "aumenta": "Aumenta",
    "cambia": "Cambia",
    "dias_sin_evaluar": "Días sin evaluar",
}
# Condiciones que admite cada indicador
CONDICIONES_POR_INDICADOR = {
    "puntuacion_ia": ("disminuye", "aumenta", "cambia"),
    "nivel_potencial": ("disminuye", "aumenta", "cambia"),
    "desempeno_previo": ("disminuye", "aumenta", "cambia"),
    "sin_evaluacion": ("dias_sin_evaluar",),
}
# El umbral son puntos (1-100), días (1-3650) o no aplica (cambio de nivel)
LIMITES_UMBRAL = {"puntuacion_ia": (1, 100), "desempeno_previo": (1, 100), "sin_evaluacion": (1, 3650)}
DIAS_POR_OMISION = 90
GRADOS = ("bajo", "medio", "alto")
MAX_NOMBRE = 80
_ORDEN_NIVEL = {nivel: indice for indice, nivel in enumerate(ia.NIVELES)}
_CAMPOS = ("nombre", "indicador", "condicion", "umbral", "area", "id_destinatario", "grado_emergencia", "activa")


def usa_umbral(indicador):
    return indicador in LIMITES_UMBRAL


def umbral_por_omision(indicador):
    if indicador == "sin_evaluacion":
        return DIAS_POR_OMISION
    with db.transaccion() as cursor:
        cursor.execute("SELECT valor FROM Configuracion_sistema WHERE clave = 'variacion_alerta_default'")
        fila = cursor.fetchone()
    return int(fila["valor"]) if fila else 10


def descripcion(regla):
    # Texto corto de la regla, p. ej. "Puntuación de IA disminuye 10 puntos o más"
    indicador = INDICADORES[regla["indicador"]]
    if regla["indicador"] == "sin_evaluacion":
        return f"{regla['umbral']} días o más sin evaluación"
    if regla["indicador"] == "nivel_potencial":
        return f"{indicador}: {CONDICIONES[regla['condicion']].lower()}"
    return f"{indicador} {CONDICIONES[regla['condicion']].lower()} {regla['umbral']} puntos o más"


# --- Configuración de reglas ---

def listar(usuario):
    # El Administrador ve todas; el Encargado, las que él recibe
    permisos.exigir(usuario, "alertas")
    condicion, parametros = ("", ()) if permisos.es_administrador(usuario) else \
        (" WHERE a.id_destinatario = %s", (usuario["id_usuario"],))
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT a.id_alerta, a.id_usuario_creador, " + ", ".join(f"a.{c}" for c in _CAMPOS)
            + ", d.nombre AS destinatario, d.activo AS destinatario_activo FROM Alertas_config a "
            "JOIN Usuarios d ON d.id_usuario = a.id_destinatario" + condicion + " ORDER BY a.nombre",
            parametros,
        )
        return cursor.fetchall()


def puede_modificar(usuario, regla):
    return permisos.es_administrador(usuario) or regla["id_usuario_creador"] == usuario["id_usuario"]


def destinatarios(usuario):
    # Administrador: cualquier usuario activo; Encargado: solo él mismo
    if not permisos.es_administrador(usuario):
        return [{"id_usuario": usuario["id_usuario"], "nombre": usuario["nombre"], "cargo": usuario["cargo"],
                 "area": usuario["area"]}]
    with db.transaccion() as cursor:
        cursor.execute("SELECT id_usuario, nombre, cargo, area FROM Usuarios WHERE activo ORDER BY cargo, nombre")
        return cursor.fetchall()


def limpiar(usuario, datos):
    limpio = {campo: datos.get(campo) for campo in _CAMPOS}
    limpio["nombre"] = str(limpio["nombre"] or "").strip()
    limpio["activa"] = bool(True if limpio["activa"] is None else limpio["activa"])
    if not permisos.es_administrador(usuario):
        # El Encargado solo configura alertas de su área y para él mismo (PRD, 6.7)
        limpio["area"] = usuario["area"]
        limpio["id_destinatario"] = usuario["id_usuario"]
    if not usa_umbral(limpio["indicador"]):
        limpio["umbral"] = None
    return limpio


def validar(usuario, datos):
    problemas = {}
    if not datos["nombre"] or len(datos["nombre"]) > MAX_NOMBRE:
        problemas["nombre"] = f"El nombre es obligatorio y admite hasta {MAX_NOMBRE} caracteres."
    if datos["indicador"] not in INDICADORES:
        problemas["indicador"] = "Seleccione el indicador."
    elif datos["condicion"] not in CONDICIONES_POR_INDICADOR[datos["indicador"]]:
        problemas["condicion"] = "Seleccione una condición válida para el indicador."
    if datos["indicador"] in LIMITES_UMBRAL:
        minimo, maximo = LIMITES_UMBRAL[datos["indicador"]]
        if not isinstance(datos["umbral"], int) or not minimo <= datos["umbral"] <= maximo:
            problemas["umbral"] = f"El umbral debe ser un número entero de {minimo} a {maximo}."
    if datos["area"] is not None and datos["area"] not in catalogos.AREAS:
        problemas["area"] = "Seleccione un área válida."
    if datos["grado_emergencia"] not in GRADOS:
        problemas["grado_emergencia"] = "Seleccione el grado de emergencia."
    destinatario = next((d for d in destinatarios(usuario) if d["id_usuario"] == datos["id_destinatario"]), None)
    if destinatario is None:
        problemas["id_destinatario"] = "Seleccione un destinatario válido."
    elif destinatario["cargo"] == permisos.ENCARGADO and datos["area"] != destinatario["area"]:
        # Un Encargado no debe recibir alertas de talentos de otra área
        problemas["area"] = f"Para un Encargado de área, el área debe ser la suya ({destinatario['area']})."
    return problemas


def crear(usuario, datos):
    # Devuelve ({campo: mensaje}, id de la regla)
    permisos.exigir(usuario, "alertas")
    datos = limpiar(usuario, datos)
    problemas = validar(usuario, datos)
    if problemas:
        return problemas, None
    with db.transaccion() as cursor:
        cursor.execute(
            "INSERT INTO Alertas_config (id_usuario_creador, " + ", ".join(_CAMPOS) + ") "
            "VALUES (%s, " + ", ".join(["%s"] * len(_CAMPOS)) + ")",
            (usuario["id_usuario"], *(datos[campo] for campo in _CAMPOS)),
        )
        id_alerta = cursor.lastrowid
        bitacora.registrar(cursor, usuario["id_usuario"], "alta", "Alertas_config", id_alerta, {"nuevo": datos})
    return {}, id_alerta


def _regla_modificable(cursor, usuario, id_alerta):
    cursor.execute("SELECT id_alerta, id_usuario_creador, " + ", ".join(_CAMPOS)
                   + " FROM Alertas_config WHERE id_alerta = %s FOR UPDATE", (id_alerta,))
    regla = cursor.fetchone()
    if regla is not None and not puede_modificar(usuario, regla):
        # El Encargado no modifica las reglas que el Administrador creó para él
        errores.registrar_aviso("E-304", {"id_usuario": usuario["id_usuario"], "id_alerta": id_alerta})
        raise errores.ErrorSistema("E-304")
    return regla


def editar(usuario, id_alerta, datos):
    permisos.exigir(usuario, "alertas")
    datos = limpiar(usuario, datos)
    problemas = validar(usuario, datos)
    if problemas:
        return problemas
    with db.transaccion() as cursor:
        regla = _regla_modificable(cursor, usuario, id_alerta)
        if regla is None:
            return {"nombre": "La alerta ya no existe."}
        cambios = {campo: datos[campo] for campo in _CAMPOS if datos[campo] != regla[campo]}
        if not cambios:
            return {}
        cursor.execute("UPDATE Alertas_config SET " + ", ".join(f"{campo} = %s" for campo in cambios)
                       + " WHERE id_alerta = %s", (*cambios.values(), id_alerta))
        bitacora.registrar(cursor, usuario["id_usuario"], "edicion", "Alertas_config", id_alerta,
                           {"anterior": {campo: regla[campo] for campo in cambios}, "nuevo": cambios})
    return {}


def cambiar_activa(usuario, id_alerta, activa):
    permisos.exigir(usuario, "alertas")
    with db.transaccion() as cursor:
        regla = _regla_modificable(cursor, usuario, id_alerta)
        if regla is None or bool(regla["activa"]) == activa:
            return
        cursor.execute("UPDATE Alertas_config SET activa = %s WHERE id_alerta = %s", (activa, id_alerta))
        bitacora.registrar(cursor, usuario["id_usuario"], "edicion", "Alertas_config", id_alerta,
                           {"anterior": {"activa": bool(regla["activa"])}, "nuevo": {"activa": activa}})


def eliminar(usuario, id_alerta):
    permisos.exigir(usuario, "alertas")
    with db.transaccion() as cursor:
        regla = _regla_modificable(cursor, usuario, id_alerta)
        if regla is None:
            return
        cursor.execute("DELETE FROM Alertas_config WHERE id_alerta = %s", (id_alerta,))
        bitacora.registrar(cursor, usuario["id_usuario"], "eliminacion", "Alertas_config", id_alerta,
                           {"anterior": {campo: regla[campo] for campo in _CAMPOS}})


def sugeridas(administrador):
    # Las reglas del PRD 6.6, para el Administrador que las crea y para todas las áreas
    umbral = umbral_por_omision("puntuacion_ia")
    base = {"area": None, "id_destinatario": administrador["id_usuario"], "activa": True}
    return [
        {**base, "nombre": f"Puntuación de IA varía {umbral} puntos", "indicador": "puntuacion_ia",
         "condicion": "cambia", "umbral": umbral, "grado_emergencia": "medio"},
        {**base, "nombre": "Cambio de nivel de potencial", "indicador": "nivel_potencial",
         "condicion": "cambia", "umbral": None, "grado_emergencia": "medio"},
        {**base, "nombre": f"Desempeño previo baja {umbral} puntos", "indicador": "desempeno_previo",
         "condicion": "disminuye", "umbral": umbral, "grado_emergencia": "alto"},
        {**base, "nombre": f"{DIAS_POR_OMISION} días sin evaluar", "indicador": "sin_evaluacion",
         "condicion": "dias_sin_evaluar", "umbral": DIAS_POR_OMISION, "grado_emergencia": "bajo"},
    ]


# --- Disparo de alertas ---

def se_cumple(regla, anterior, nuevo):
    # Reglas de variación; anterior y nuevo son puntos (0-100) o niveles (bajo/medio/alto)
    if anterior is None or nuevo is None:
        return False
    if regla["indicador"] == "nivel_potencial":
        diferencia = _ORDEN_NIVEL[nuevo] - _ORDEN_NIVEL[anterior]
        umbral = 1
    else:
        diferencia = nuevo - anterior
        umbral = regla["umbral"]
    if regla["condicion"] == "disminuye":
        return -diferencia >= umbral
    if regla["condicion"] == "aumenta":
        return diferencia >= umbral
    return abs(diferencia) >= umbral


def _reglas_activas(cursor, indicador, area):
    cursor.execute(
        "SELECT a.id_alerta, a.nombre, a.indicador, a.condicion, a.umbral, a.id_destinatario, a.grado_emergencia "
        "FROM Alertas_config a JOIN Usuarios u ON u.id_usuario = a.id_destinatario "
        "WHERE a.activa AND u.activo AND a.indicador = %s AND (a.area IS NULL OR a.area = %s)",
        (indicador, area),
    )
    return cursor.fetchall()


def _crear_notificacion(cursor, regla, id_talento, contenido):
    cursor.execute(
        "INSERT INTO Notificaciones (id_destinatario, contenido, tipo, id_talento, grado_emergencia) "
        "VALUES (%s, %s, 'alerta_automatica', %s, %s)",
        (regla["id_destinatario"], contenido, id_talento, regla["grado_emergencia"]),
    )


def _encabezado(regla, talento):
    return f"Alerta \"{regla['nombre']}\": {talento['nombre']} (ID {talento['id_talento']}, {talento['area']})"


def al_evaluar(cursor, talento, anterior, nueva):
    # Después de guardar una evaluación; anterior es la evaluación previa o None.
    # Devuelve el número de alertas creadas.
    creadas = 0
    if anterior is None:
        return creadas
    cambios = {
        "puntuacion_ia": (anterior["puntuacion_talento_por_ia"], nueva["puntuacion_talento_por_ia"],
                          "la puntuación de IA pasó de {} a {} puntos."),
        "nivel_potencial": (anterior["potencial_crecimiento_nivel"], nueva["potencial_crecimiento_nivel"],
                            "el nivel de potencial pasó de {} a {}."),
    }
    for indicador, (antes, despues, plantilla) in cambios.items():
        for regla in _reglas_activas(cursor, indicador, talento["area"]):
            if se_cumple(regla, antes, despues):
                _crear_notificacion(cursor, regla, talento["id_talento"],
                                    f"{_encabezado(regla, talento)}: {plantilla.format(antes, despues)}")
                creadas += 1
    return creadas


def al_editar(cursor, talento, desempeno_anterior, desempeno_nuevo):
    # Después de guardar la edición de un talento (con su área ya actualizada)
    creadas = 0
    for regla in _reglas_activas(cursor, "desempeno_previo", talento["area"]):
        if se_cumple(regla, desempeno_anterior, desempeno_nuevo):
            _crear_notificacion(cursor, regla, talento["id_talento"],
                                f"{_encabezado(regla, talento)}: el desempeño previo pasó de "
                                f"{desempeno_anterior} a {desempeno_nuevo}.")
            creadas += 1
    return creadas


def revisar_sin_evaluar(hoy=None):
    # Al iniciar sesión (PRD, 12.3). Para no repetir avisos, un talento genera una sola
    # alerta por regla desde su última evaluación (o desde su ingreso si no tiene).
    hoy = hoy or datetime.date.today()
    creadas = 0
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT a.id_alerta, a.nombre, a.umbral, a.area, a.id_destinatario, a.grado_emergencia "
            "FROM Alertas_config a JOIN Usuarios u ON u.id_usuario = a.id_destinatario "
            "WHERE a.activa AND u.activo AND a.indicador = 'sin_evaluacion'"
        )
        for regla in cursor.fetchall():
            cursor.execute(
                "SELECT t.id_talento, t.nombre, t.area, "
                "COALESCE(MAX(e.fecha_evaluacion), t.fecha_ingreso) AS referencia, "
                "MAX(e.fecha_evaluacion) AS ultima FROM Talentos t "
                "LEFT JOIN Evaluaciones e ON e.id_talento = t.id_talento "
                "WHERE t.activo AND (%s IS NULL OR t.area = %s) GROUP BY t.id_talento "
                "HAVING referencia <= %s",
                (regla["area"], regla["area"], hoy - datetime.timedelta(days=regla["umbral"])),
            )
            for talento in cursor.fetchall():
                encabezado = _encabezado(regla, talento)
                cursor.execute(
                    "SELECT 1 FROM Notificaciones WHERE tipo = 'alerta_automatica' AND id_destinatario = %s "
                    "AND id_talento = %s AND contenido LIKE %s AND DATE(fecha_creacion) >= %s LIMIT 1",
                    (regla["id_destinatario"], talento["id_talento"], f"Alerta \"{regla['nombre']}\":%",
                     talento["referencia"]),
                )
                if cursor.fetchone():
                    continue
                dias = (hoy - talento["referencia"]).days
                detalle = (f"lleva {dias} días sin evaluación con IA (última: {talento['ultima']:%d/%m/%Y})."
                           if talento["ultima"] else f"lleva {dias} días desde su ingreso sin evaluación con IA.")
                _crear_notificacion(cursor, regla, talento["id_talento"], f"{encabezado}: {detalle}")
                creadas += 1
    return creadas
