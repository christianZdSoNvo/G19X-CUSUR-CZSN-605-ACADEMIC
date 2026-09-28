import json


def registrar(cursor, id_usuario, accion, tabla=None, id_registro=None, detalle=None):
    # Recibe el cursor para guardarse en la misma transacción que la acción
    cursor.execute(
        "INSERT INTO Bitacora (id_usuario, accion, tabla_afectada, id_registro_afectado, detalle) "
        "VALUES (%s, %s, %s, %s, %s)",
        (id_usuario, accion, tabla, id_registro,
         json.dumps(detalle, ensure_ascii=False) if detalle else None),
    )
