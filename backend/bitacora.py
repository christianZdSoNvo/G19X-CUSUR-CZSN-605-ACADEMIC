import json

from backend import db, permisos


def registrar(cursor, id_usuario, accion, tabla=None, id_registro=None, detalle=None):
    # Recibe el cursor para guardarse en la misma transacción que la acción;
    # default=str convierte las fechas del detalle a texto (AAAA-MM-DD)
    cursor.execute(
        "INSERT INTO Bitacora (id_usuario, accion, tabla_afectada, id_registro_afectado, detalle) "
        "VALUES (%s, %s, %s, %s, %s)",
        (id_usuario, accion, tabla, id_registro,
         json.dumps(detalle, ensure_ascii=False, default=str) if detalle else None),
    )


# Consulta de la bitácora (PRD, 13.4): solo Administrador, con filtros por usuario,
# acción y fecha. Como se muestran en pantalla:
ACCIONES = {
    "inicio_sesion": "Inicio de sesión",
    "cierre_sesion": "Cierre de sesión",
    "intento_fallido": "Intento fallido",
    "alta": "Alta",
    "edicion": "Edición",
    "baja": "Baja",
    "eliminacion": "Eliminación",
    "evaluacion_ia": "Evaluación con IA",
    "exportacion": "Exportación",
    "configuracion": "Configuración",
}
SIN_USUARIO = 0
MAX_FILAS = 2000


def consultar(usuario, desde, hasta, id_usuario=None, acciones=None, tabla=None, limite=MAX_FILAS):
    # id_usuario=SIN_USUARIO busca los intentos con un usuario inexistente (id_usuario NULL).
    # Devuelve las filas más recientes primero, hasta "limite" (+1 para saber si hay más).
    permisos.exigir(usuario, "bitacora")
    condiciones = ["b.fecha_hora >= %s", "b.fecha_hora < %s + INTERVAL 1 DAY"]
    valores = [desde, hasta]
    if id_usuario == SIN_USUARIO:
        condiciones.append("b.id_usuario IS NULL")
    elif id_usuario is not None:
        condiciones.append("b.id_usuario = %s")
        valores.append(id_usuario)
    if acciones:
        condiciones.append(f"b.accion IN ({', '.join(['%s'] * len(acciones))})")
        valores += list(acciones)
    if tabla:
        condiciones.append("b.tabla_afectada = %s")
        valores.append(tabla)
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT b.id_bitacora, b.fecha_hora, b.id_usuario, u.nombre, u.usuario, b.accion, "
            "b.tabla_afectada, b.id_registro_afectado, b.detalle "
            "FROM Bitacora b LEFT JOIN Usuarios u ON u.id_usuario = b.id_usuario "
            f"WHERE {' AND '.join(condiciones)} ORDER BY b.id_bitacora DESC LIMIT %s",
            (*valores, limite + 1),
        )
        return cursor.fetchall()


def tablas(usuario):
    permisos.exigir(usuario, "bitacora")
    with db.transaccion() as cursor:
        cursor.execute("SELECT DISTINCT tabla_afectada FROM Bitacora WHERE tabla_afectada IS NOT NULL "
                       "ORDER BY tabla_afectada")
        return [fila["tabla_afectada"] for fila in cursor.fetchall()]
