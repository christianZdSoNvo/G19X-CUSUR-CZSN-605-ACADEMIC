from contextlib import contextmanager

import mysql.connector

from backend import config, errores


def obtener_conexion(con_base_de_datos=True):
    parametros = {
        "host": config.DB_HOST,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
    }
    if con_base_de_datos:
        parametros["database"] = config.DB_NAME
    return mysql.connector.connect(**parametros)


def probar_conexion():

    conexion = obtener_conexion(con_base_de_datos=False)
    try:
        cursor = conexion.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        cursor.execute("SHOW DATABASES LIKE %s", (config.DB_NAME,))
        existe = cursor.fetchone() is not None
        cursor.close()
        return version, existe
    finally:
        conexion.close()


def codigo_de_error(error):
    # Traduce un error de MySQL a un código del catálogo
    if error.errno in (1044, 1045, 1049, 1142):
        return "E-002"
    if error.errno == 1062:
        return "E-004"
    if isinstance(error, (mysql.connector.IntegrityError, mysql.connector.DataError)) or error.errno == 3819:
        return "E-003"
    return "E-001"


@contextmanager
def transaccion():
    # Cursor de diccionarios; confirma al salir sin errores y deshace si hay una excepción
    conexion = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True, buffered=True)
        yield cursor
        conexion.commit()
    except mysql.connector.Error as error:
        codigo = codigo_de_error(error)
        errores.registrar(codigo, error)
        raise errores.ErrorSistema(codigo) from error
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()
