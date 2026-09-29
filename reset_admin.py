"""Restablece la contraseña de un Administrador de RH desde el servidor (PRD, 6.7).

Uso (en la carpeta del proyecto):
    .venv\\Scripts\\python.exe reset_admin.py
    .venv\\Scripts\\python.exe reset_admin.py --usuario <usuario>

Genera una contraseña temporal, desbloquea la cuenta, obliga a cambiarla en el
siguiente inicio de sesión y deja el registro en la bitácora.
"""

import argparse
import sys

from backend import db, errores, permisos, usuarios


def administradores_activos():
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_usuario, nombre, usuario FROM Usuarios WHERE cargo = %s AND activo ORDER BY usuario",
            (permisos.ADMINISTRADOR,),
        )
        return cursor.fetchall()


def elegir(administradores, usuario=None):
    # Devuelve (administrador, None) o (None, mensaje de error)
    if not administradores:
        return None, "No hay ningún Administrador de RH activo en la base de datos."
    if usuario is None:
        if len(administradores) == 1:
            return administradores[0], None
        nombres = ", ".join(a["usuario"] for a in administradores)
        return None, f"Hay varios Administradores ({nombres}). Indique cuál con --usuario."
    for administrador in administradores:
        if administrador["usuario"] == usuario:
            return administrador, None
    return None, f"'{usuario}' no es un Administrador de RH activo."


def main():
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--usuario", help="usuario del Administrador (si hay más de uno)")
    usuario = argumentos.parse_args().usuario

    try:
        administrador, problema = elegir(administradores_activos(), usuario)
        if problema:
            print(problema)
            return 1

        print(f"Se restablecerá la contraseña de {administrador['nombre']} "
              f"(usuario: {administrador['usuario']}).")
        if input("¿Continuar? (s/n): ").strip().lower() != "s":
            print("Cancelado; no se hizo ningún cambio.")
            return 1

        # El propio Administrador queda como autor: el script no tiene sesión
        temporal = usuarios.restablecer_contrasena(administrador, administrador["id_usuario"],
                                                   origen="reset_admin.py")
    except errores.ErrorSistema as error:
        print(f"{error.mensaje} (código {error.codigo})")
        return 1

    print(f"\nContraseña temporal: {temporal}")
    print("Deberá cambiarla en el siguiente inicio de sesión. La acción quedó en la bitácora.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
