from backend import permisos

# Menú del sistema: sección -> (archivo, título, ícono, función de la matriz de permisos)
MENU = {
    "": [
        ("paginas/inicio.py", "Inicio", ":material/home:", None),
    ],
    "Talentos": [
        ("paginas/talentos.py", "Talentos", ":material/groups:", "ver_talentos"),
        ("paginas/paneles.py", "Paneles analíticos", ":material/monitoring:", "paneles"),
        ("paginas/reportes.py", "Reportes", ":material/description:", "reportes"),
        ("paginas/historial.py", "Historial y evolución", ":material/timeline:", "historial"),
    ],
    "Seguimiento": [
        ("paginas/notificaciones.py", "Notificaciones y alertas", ":material/notifications:", "notificaciones"),
    ],
    "Configuración": [
        ("paginas/configuracion.py", "Configuración", ":material/settings:", "configuracion_general"),
        ("paginas/gestion_usuarios.py", "Gestión de usuarios", ":material/manage_accounts:", "gestion_usuarios"),
        ("paginas/parametros.py", "Parámetros del sistema", ":material/tune:", "parametros"),
        ("paginas/manuales.py", "Manuales", ":material/menu_book:", "consultar_manuales"),
        ("paginas/bitacora.py", "Bitácora", ":material/history:", "bitacora"),
    ],
    "Ayuda": [
        ("paginas/soporte.py", "Soporte", ":material/support_agent:", "soporte"),
    ],
}


def opciones(usuario):
    # Todas las páginas se registran para que una URL no permitida llegue a su
    # página y muestre E-304; las que el rol no puede usar quedan ocultas del menú.
    for seccion, paginas in MENU.items():
        for archivo, titulo, icono, funcion in paginas:
            visible = funcion is None or permisos.puede(usuario, funcion)
            yield seccion, archivo, titulo, icono, visible
