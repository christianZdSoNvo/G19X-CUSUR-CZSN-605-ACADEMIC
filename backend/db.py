import mysql.connector

from backend import config


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
