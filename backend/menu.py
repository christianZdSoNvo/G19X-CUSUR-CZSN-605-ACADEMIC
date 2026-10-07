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


NOTIFICACIONES = "paginas/notificaciones.py"
PANELES_ANALITICOS = "paginas/paneles.py"
CLAVE_PANELES = "paneles_elegidos"

# Paneles que se eligen en el menú, justo debajo de "Paneles analíticos" (sin elegir
# ninguno se muestran todos), con la explicación que va debajo de cada uno
PANELES = {
    "Indicadores": "Resumen del grupo filtrado: talentos activos, porcentaje con potencial alto en su última "
                   "evaluación, evaluaciones con IA hechas en el mes en curso y talentos que aún no tienen "
                   "evaluación.",
    "Distribución por nivel de potencial": "Cuántos talentos de cada área tienen potencial bajo, medio o alto "
                                           "según su última evaluación con IA. Sirve para comparar en qué áreas "
                                           "se concentra el talento de alto potencial.",
    "Matriz 9-box": "Cruza el desempeño previo (eje horizontal) con el potencial de crecimiento (eje vertical) y "
                    "cuenta los talentos de cada una de las 9 celdas. Arriba a la derecha están las \"Altas "
                    "estrellas\"; abajo a la izquierda, quienes \"Necesitan mejora\".",
    "Promedio de puntuación por área": "Puntuación de IA promedio (0 a 100) de la última evaluación de los "
                                       "talentos de cada área.",
    "Histograma de puntuaciones": "Cuántos talentos hay en cada rango de 10 puntos de la puntuación de IA; "
                                  "muestra si las puntuaciones se concentran en valores bajos, medios o altos.",
    "Evolución mensual": "Promedio de las puntuaciones de todas las evaluaciones con IA hechas en cada mes; "
                         "permite ver si el grupo mejora o baja con el tiempo.",
    "Comparación entre talentos": "Compara el nivel de cada criterio de la última evaluación de hasta 5 "
                                  "talentos (Alto = 3, Medio = 2, Bajo = 1). Mientras más amplia es la figura, "
                                  "mejores son sus niveles.",
}


def opciones(usuario, pendientes=0):
    # Todas las páginas se registran para que una URL no permitida llegue a su
    # página y muestre E-304; las que el rol no puede usar no aparecen en el menú (visible=False).
    # Notificaciones muestra el número de pendientes (PRD, 12.3).
    for seccion, paginas in MENU.items():
        for archivo, titulo, icono, funcion in paginas:
            visible = funcion is None or permisos.puede(usuario, funcion)
            if archivo == NOTIFICACIONES and pendientes:
                titulo = f"{titulo} ({pendientes})"
            yield seccion, archivo, titulo, icono, visible


def accesos(usuario, pendientes=0):
    # Accesos de la pantalla de Inicio: {sección: [(archivo, título, ícono)]}, sin Inicio
    # y sin las páginas que el rol no puede usar
    agrupado = {}
    for seccion, archivo, titulo, icono, visible in opciones(usuario, pendientes):
        if visible and seccion:
            agrupado.setdefault(seccion, []).append((archivo, titulo, icono))
    return agrupado
