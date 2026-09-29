import json


def registrar(cursor, id_usuario, accion, tabla=None, id_registro=None, detalle=None):
    # Recibe el cursor para guardarse en la misma transacción que la acción;
    # default=str convierte las fechas del detalle a texto (AAAA-MM-DD)
    cursor.execute(
        "INSERT INTO Bitacora (id_usuario, accion, tabla_afectada, id_registro_afectado, detalle) "
        "VALUES (%s, %s, %s, %s, %s)",
        (id_usuario, accion, tabla, id_registro,
         json.dumps(detalle, ensure_ascii=False, default=str) if detalle else None),
    )
