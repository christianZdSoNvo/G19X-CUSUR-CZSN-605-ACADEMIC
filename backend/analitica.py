import datetime

import pandas as pd

from backend import db, evaluaciones, ia, permisos

# Datos y cálculos de los paneles analíticos (PRD, 13.1) y del historial (PRD, 13.3).
# Las consultas reciben al usuario de la sesión para limitar al Encargado a su área;
# los cálculos trabajan sobre DataFrames y no tocan la BD, para poder probarlos.

NIVELES = ("bajo", "medio", "alto")
NOMBRES_CRITERIOS = {
    "desempeno_pre_ev": "Desempeño previo",
    "resultados_cap_ev": "Resultados de capacitación",
    "experiencia_lab_ev": "Experiencia laboral",
    "objetivos_fut_ev": "Objetivos futuros",
    "competencias_ev": "Competencias",
    "liderazgo_prev_ev": "Liderazgo previo",
}
# Radar: Alto = 3, Medio = 2, Bajo = 1 (PRD, 13.1)
VALOR_NIVEL = {"bajo": 1, "medio": 2, "alto": 3}
CLASIFICACIONES = (*evaluaciones.MATRIZ_9BOX.values(), evaluaciones.SIN_CLASIFICAR)
RANGOS_HISTOGRAMA = [f"{inicio}-{inicio + 9}" for inicio in range(0, 90, 10)] + ["90-100"]
MAX_RADAR = 5
# Cómo se muestra cada tipo de Eventos_talento (en la BD va sin acentos)
TIPOS_EVENTO = {
    "ingreso": "Ingreso",
    "promocion": "Promoción",
    "capacitacion": "Capacitación",
    "cambio_area": "Cambio de área",
    "cambio_desempeno": "Cambio de desempeño",
    "evaluacion_ia": "Evaluación con IA",
    "cambio_clasificacion": "Cambio de clasificación",
    "otro": "Otro",
}

_COLUMNAS_TALENTO = ("id_talento", "nombre", "area", "fecha_ingreso", "desempeno_previo")
_COLUMNAS_EVALUACION = ("id_evaluacion", "fecha_evaluacion", "puntuacion_talento_por_ia",
                        "potencial_crecimiento_nivel", "clasificacion_9box", *ia.CRITERIOS)


# --- Consultas ---

def _condicion_area(usuario):
    area = permisos.area_permitida(usuario)
    return (" AND t.area = %s", (area,)) if area else ("", ())


def talentos_con_ultima_evaluacion(usuario):
    # Un renglón por talento activo con su última evaluación (columnas vacías si no tiene)
    condicion, parametros = _condicion_area(usuario)
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT " + ", ".join(f"t.{c}" for c in _COLUMNAS_TALENTO) + ", "
            + ", ".join(f"e.{c}" for c in _COLUMNAS_EVALUACION) + " FROM Talentos t "
            "LEFT JOIN Evaluaciones e ON e.id_evaluacion = "
            "(SELECT MAX(id_evaluacion) FROM Evaluaciones WHERE id_talento = t.id_talento) "
            "WHERE t.activo" + condicion + " ORDER BY t.nombre",
            parametros,
        )
        filas = cursor.fetchall()
    return pd.DataFrame(filas, columns=[*_COLUMNAS_TALENTO, *_COLUMNAS_EVALUACION])


def todas_las_evaluaciones(usuario):
    # Todas las evaluaciones de los talentos activos (para la evolución mensual)
    condicion, parametros = _condicion_area(usuario)
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT e.id_talento, e.fecha_evaluacion, e.puntuacion_talento_por_ia FROM Evaluaciones e "
            "JOIN Talentos t ON t.id_talento = e.id_talento WHERE t.activo" + condicion,
            parametros,
        )
        filas = cursor.fetchall()
    return pd.DataFrame(filas, columns=["id_talento", "fecha_evaluacion", "puntuacion_talento_por_ia"])


def historial(usuario, id_talento):
    # Evaluaciones y eventos de un talento, del más antiguo al más reciente (PRD, 9.10)
    with db.transaccion() as cursor:
        cursor.execute("SELECT area FROM Talentos WHERE id_talento = %s", (id_talento,))
        talento = cursor.fetchone()
        if talento is None:
            return None
        permisos.exigir_area(usuario, talento["area"])
        cursor.execute(
            "SELECT id_evaluacion, fecha_evaluacion, puntuacion_talento_por_ia, potencial_crecimiento_nivel, "
            "clasificacion_9box FROM Evaluaciones WHERE id_talento = %s ORDER BY id_evaluacion",
            (id_talento,),
        )
        evaluaciones_talento = cursor.fetchall()
        cursor.execute(
            "SELECT id_evento, tipo_evento, descripcion, fecha_evento FROM Eventos_talento "
            "WHERE id_talento = %s ORDER BY fecha_evento, id_evento",
            (id_talento,),
        )
        eventos = cursor.fetchall()
    return {"evaluaciones": evaluaciones_talento, "eventos": eventos}


# --- Cálculos ---

def antiguedad_anios(fecha_ingreso, hoy=None):
    hoy = hoy or datetime.date.today()
    return (hoy - fecha_ingreso).days / 365.25


def filtrar(datos, area=None, niveles=(), clasificaciones=(), fechas=None, puntuacion=None, antiguedad=None,
            hoy=None):
    # Filtros del panel (PRD, 13.1). Los que dependen de la evaluación (nivel, 9-box,
    # fechas y puntuación) dejan fuera a los talentos sin evaluar.
    filtro = pd.Series(True, index=datos.index)
    if area:
        filtro &= datos["area"] == area
    if niveles:
        filtro &= datos["potencial_crecimiento_nivel"].isin(niveles)
    if clasificaciones:
        filtro &= datos["clasificacion_9box"].isin(clasificaciones)
    if fechas:
        desde, hasta = fechas
        filtro &= datos["fecha_evaluacion"].map(lambda f: not pd.isna(f) and desde <= f <= hasta).astype(bool)
    if puntuacion:
        minimo, maximo = puntuacion
        filtro &= datos["puntuacion_talento_por_ia"].between(minimo, maximo)
    if antiguedad:
        minimo, maximo = antiguedad
        anios = datos["fecha_ingreso"].map(lambda f: antiguedad_anios(f, hoy))
        filtro &= anios.between(minimo, maximo)
    return datos[filtro.fillna(False).astype(bool)]


def evaluados(datos):
    return datos[datos["id_evaluacion"].notna()]


def indicadores(datos, todas, hoy=None):
    # Tarjetas: total de talentos, % con potencial alto, evaluaciones del mes y sin evaluar
    hoy = hoy or datetime.date.today()
    con_evaluacion = evaluados(datos)
    altos = (con_evaluacion["potencial_crecimiento_nivel"] == "alto").sum()
    del_grupo = todas[todas["id_talento"].isin(datos["id_talento"])]
    del_mes = del_grupo["fecha_evaluacion"].map(lambda f: (f.year, f.month) == (hoy.year, hoy.month))
    return {
        "total": len(datos),
        "porcentaje_alto": round(100 * altos / len(con_evaluacion), 1) if len(con_evaluacion) else None,
        "evaluaciones_mes": int(del_mes.sum()),
        "sin_evaluar": len(datos) - len(con_evaluacion),
    }


def distribucion_por_area(datos):
    # Talentos por área y nivel de potencial (columnas bajo, medio, alto)
    tabla = pd.crosstab(evaluados(datos)["area"], evaluados(datos)["potencial_crecimiento_nivel"])
    return tabla.reindex(columns=list(NIVELES), fill_value=0)


def conteo_9box(datos):
    # {clasificación: número de talentos}, con las 9 celdas aunque estén vacías
    conteo = evaluados(datos)["clasificacion_9box"].value_counts()
    return {clasificacion: int(conteo.get(clasificacion, 0)) for clasificacion in CLASIFICACIONES}


def promedio_por_area(datos):
    con_evaluacion = evaluados(datos)
    if con_evaluacion.empty:
        return pd.Series(dtype=float)
    return con_evaluacion.groupby("area")["puntuacion_talento_por_ia"].mean().round(1).sort_values()


def histograma(datos):
    # Número de talentos por rango de 10 puntos (el último rango incluye el 100)
    puntuaciones = evaluados(datos)["puntuacion_talento_por_ia"].astype(int)
    rangos = puntuaciones.map(lambda p: RANGOS_HISTOGRAMA[min(p // 10, 9)])
    return rangos.value_counts().reindex(RANGOS_HISTOGRAMA, fill_value=0)


def evolucion_mensual(datos, todas, fechas=None):
    # Promedio mensual de las puntuaciones de todas las evaluaciones del grupo filtrado
    grupo = todas[todas["id_talento"].isin(datos["id_talento"])]
    if fechas:
        desde, hasta = fechas
        grupo = grupo[grupo["fecha_evaluacion"].map(lambda f: desde <= f <= hasta)]
    if grupo.empty:
        return pd.Series(dtype=float)
    meses = grupo["fecha_evaluacion"].map(lambda f: f"{f.year}-{f.month:02d}")
    return grupo.groupby(meses)["puntuacion_talento_por_ia"].mean().round(1).sort_index()


def valores_radar(fila):
    # Nivel de cada criterio convertido a 1-3 para la gráfica de radar
    return {nombre: VALOR_NIVEL[fila[llave]] for llave, nombre in NOMBRES_CRITERIOS.items()}
