import math

import pandas as pd
import streamlit as st

from backend import analitica, catalogos, evaluaciones, graficas, menu, permisos, sesion, talentos, vistas

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "paneles")
st.set_page_config(layout="wide")

FILTROS = ("filtro_area", "filtro_niveles", "filtro_9box", "filtro_fechas", "filtro_puntuacion", "filtro_antiguedad")

# Paneles elegidos en el menú (app.py los pone debajo de "Paneles analíticos"); sin elegir
# ninguno se muestran todos
elegidos = st.session_state.get(menu.CLAVE_PANELES) or list(menu.PANELES)


def nombre_nivel(nivel):
    return graficas.NOMBRE_NIVEL[nivel]


def ver(nombre):
    return nombre in elegidos


def explicar(nombre):
    st.caption(menu.PANELES[nombre])


def lado_a_lado(izquierdo, derecho):
    # Si se muestran los dos paneles del renglón, uno junto al otro; si solo uno, a todo lo ancho
    if ver(izquierdo) and ver(derecho):
        return st.columns(2)
    return [st.container() if ver(izquierdo) else None, st.container() if ver(derecho) else None]


# --- Drill-down (PRD, 13.1): área -> nivel -> talentos -> perfil; celda del 9-box -> talentos ---
# La selección se guarda en session_state; la versión cambia la clave de las gráficas
# para que la selección anterior de Plotly no se vuelva a aplicar.

def seleccion():
    return st.session_state.get("panel_seleccion", {})


def seleccionar(nueva):
    st.session_state["panel_seleccion"] = nueva
    st.session_state["panel_version"] = st.session_state.get("panel_version", 0) + 1
    st.rerun()


def clave(nombre):
    return f"{nombre}_{st.session_state.get('panel_version', 0)}"


def punto(evento, campo):
    puntos = evento.selection.points if evento else []
    if not puntos:
        return None
    valor = puntos[0].get(campo)
    return valor[0] if isinstance(valor, list) else valor


def grafica_distribucion(datos):
    actual = seleccion()
    area = actual.get("area")
    if area:
        st.markdown(f"**{area}: talentos por nivel de potencial**")
        del_area = analitica.evaluados(datos)
        conteo = del_area[del_area["area"] == area]["potencial_crecimiento_nivel"].value_counts()
        evento = st.plotly_chart(graficas.barras_nivel(conteo), key=clave("niveles"), on_select="rerun",
                                 selection_mode="points")
        nivel = punto(evento, "customdata")
        if nivel:
            seleccionar({"area": area, "nivel": nivel})
        if st.button("← Todas las áreas", key="volver_areas"):
            seleccionar({})
        explicar("Distribución por nivel de potencial")
        st.caption("Haga clic en una barra para ver la lista de talentos de ese nivel.")
    else:
        st.markdown("**Distribución por nivel de potencial**")
        evento = st.plotly_chart(graficas.distribucion(analitica.distribucion_por_area(datos)), key=clave("areas"),
                                 on_select="rerun", selection_mode="points")
        area = punto(evento, "x")
        if area:
            seleccionar({"area": area})
        explicar("Distribución por nivel de potencial")
        st.caption("Haga clic en un área para ver su desglose por nivel.")


def grafica_9box(datos):
    st.markdown("**Matriz 9-box**")
    conteo = analitica.conteo_9box(datos)
    evento = st.plotly_chart(graficas.matriz_9box(conteo), key=clave("9box"), on_select="rerun",
                             selection_mode="points")
    celda = punto(evento, "customdata")
    if celda:
        seleccionar({"celda": celda})
    sin_clasificar = conteo[evaluaciones.SIN_CLASIFICAR]
    explicar("Matriz 9-box")
    st.caption("Haga clic en una celda para ver sus talentos."
               + (f" Sin clasificar (sin desempeño previo): {sin_clasificar}." if sin_clasificar else ""))


def detalle(datos):
    # Lista de talentos del grupo elegido y perfil con su historial
    actual = seleccion()
    evaluados = analitica.evaluados(datos)
    if "celda" in actual:
        grupo = evaluados[evaluados["clasificacion_9box"] == actual["celda"]]
        titulo = f"Talentos en \"{actual['celda']}\""
    elif "nivel" in actual:
        grupo = evaluados[(evaluados["area"] == actual["area"])
                          & (evaluados["potencial_crecimiento_nivel"] == actual["nivel"])]
        titulo = f"{actual['area']}: potencial {actual['nivel']}"
    else:
        return

    st.divider()
    encabezado, quitar = st.columns([4, 1])
    encabezado.subheader(titulo)
    if quitar.button("Quitar selección", width="stretch"):
        seleccionar({})
    if grupo.empty:
        st.info("No hay talentos en este grupo con los filtros actuales.")
        return

    grupo = grupo.sort_values("puntuacion_talento_por_ia", ascending=False)
    tabla = st.dataframe(pd.DataFrame({
        "ID": grupo["id_talento"],
        "Nombre": grupo["nombre"],
        "Área": grupo["area"],
        "Puntuación": grupo["puntuacion_talento_por_ia"].astype(int),
        "Potencial": grupo["potencial_crecimiento_nivel"].map(nombre_nivel),
        "Clasificación 9-box": grupo["clasificacion_9box"],
        "Última evaluación": grupo["fecha_evaluacion"].map(vistas.fecha),
    }), hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key=clave("grupo"))
    st.caption("Seleccione un renglón para ver el perfil del talento con su historial.")
    filas = tabla.selection.rows
    if not filas:
        return

    talento = grupo.iloc[filas[0]]
    vistas.encabezado_talento(talentos.obtener(usuario, int(talento["id_talento"])),
                              f"{talento['area']} · Ingreso: {vistas.fecha(talento['fecha_ingreso'])}")
    potencial, puntuacion, desempeno = st.columns(3)
    potencial.metric("Potencial de crecimiento", nombre_nivel(talento["potencial_crecimiento_nivel"]))
    puntuacion.metric("Puntuación", int(talento["puntuacion_talento_por_ia"]))
    desempeno.metric("Desempeño previo",
                     "Sin registro" if pd.isna(talento["desempeno_previo"]) else int(talento["desempeno_previo"]))
    st.markdown(f"**Clasificación 9-box:** {talento['clasificacion_9box']}")
    vistas.historial_talento(usuario, {"id_talento": int(talento["id_talento"]),
                                       "fecha_ingreso": talento["fecha_ingreso"]}, clave("perfil"))
    if st.button("Abrir en Historial y evolución"):
        st.session_state["historial_talento"] = int(talento["id_talento"])
        st.switch_page("paginas/historial.py")


# --- Página ---

st.title("Paneles analíticos")
datos = analitica.talentos_con_ultima_evaluacion(usuario)
if datos.empty:
    st.info("No hay talentos registrados.")
    st.stop()
todas = analitica.todas_las_evaluaciones(usuario)

with st.container(border=True):
    st.markdown("**Filtros**")
    fila1 = st.columns(3)
    area_fija = permisos.area_permitida(usuario)
    if area_fija:
        fila1[0].text_input("Área", area_fija, disabled=True)
        area = area_fija
    else:
        area = fila1[0].selectbox("Área", catalogos.AREAS, index=None, placeholder="Todas las áreas",
                                  key="filtro_area")
    niveles = fila1[1].multiselect("Nivel de potencial", analitica.NIVELES, format_func=nombre_nivel,
                                   placeholder="Todos", key="filtro_niveles")
    clasificaciones = fila1[2].multiselect("Clasificación 9-box", analitica.CLASIFICACIONES, placeholder="Todas",
                                           key="filtro_9box")
    fila2 = st.columns(3)
    fechas = fila2[0].date_input("Fechas de evaluación", value=(), format="DD/MM/YYYY", key="filtro_fechas")
    puntuacion = fila2[1].slider("Puntuación de IA", 0, 100, (0, 100), key="filtro_puntuacion")
    maximo_anios = max(1, math.ceil(datos["fecha_ingreso"].map(analitica.antiguedad_anios).max()))
    antiguedad = fila2[2].slider("Antigüedad (años)", 0, maximo_anios, (0, maximo_anios), key="filtro_antiguedad")
    if st.button("Limpiar filtros"):
        for filtro in FILTROS:
            st.session_state.pop(filtro, None)
        seleccionar({})

# Solo se aplican los filtros que el usuario cambió
fechas = tuple(fechas) if len(fechas) == 2 else None
filtrado = analitica.filtrar(
    datos, area=area, niveles=niveles, clasificaciones=clasificaciones, fechas=fechas,
    puntuacion=puntuacion if puntuacion != (0, 100) else None,
    antiguedad=antiguedad if antiguedad != (0, maximo_anios) else None,
)
if filtrado.empty:
    st.warning("Ningún talento cumple con los filtros seleccionados.")
    st.stop()

resumen = analitica.indicadores(filtrado, todas)
if ver("Indicadores"):
    tarjetas = st.columns(4)
    tarjetas[0].metric("Talentos activos", resumen["total"])
    tarjetas[1].metric("Con potencial alto",
                       "Sin evaluaciones" if resumen["porcentaje_alto"] is None else f"{resumen['porcentaje_alto']} %")
    tarjetas[2].metric("Evaluaciones del mes", resumen["evaluaciones_mes"])
    tarjetas[3].metric("Talentos sin evaluar", resumen["sin_evaluar"])
    explicar("Indicadores")
if elegidos == ["Indicadores"]:
    st.stop()

if analitica.evaluados(filtrado).empty:
    st.info("Aún no hay evaluaciones con IA en este grupo; las gráficas aparecerán después de evaluar talentos.")
    st.stop()

if ver("Distribución por nivel de potencial") or ver("Matriz 9-box"):
    izquierda, derecha = lado_a_lado("Distribución por nivel de potencial", "Matriz 9-box")
    if izquierda:
        with izquierda:
            grafica_distribucion(filtrado)
    if derecha:
        with derecha:
            grafica_9box(filtrado)
    detalle(filtrado)

if ver("Promedio de puntuación por área") or ver("Histograma de puntuaciones"):
    if ver("Distribución por nivel de potencial") or ver("Matriz 9-box"):
        st.divider()
    izquierda, derecha = lado_a_lado("Promedio de puntuación por área", "Histograma de puntuaciones")
    if izquierda:
        with izquierda:
            st.markdown("**Promedio de puntuación de IA por área**")
            st.plotly_chart(graficas.promedio_por_area(analitica.promedio_por_area(filtrado)), key="promedios")
            explicar("Promedio de puntuación por área")
    if derecha:
        with derecha:
            st.markdown("**Histograma de puntuaciones de IA**")
            st.plotly_chart(graficas.histograma(analitica.histograma(filtrado)), key="histograma")
            explicar("Histograma de puntuaciones")

if ver("Evolución mensual"):
    st.markdown("**Evolución mensual del promedio de puntuación**")
    st.plotly_chart(graficas.evolucion(analitica.evolucion_mensual(filtrado, todas, fechas)), key="evolucion")
    explicar("Evolución mensual")

if ver("Comparación entre talentos"):
    st.markdown("**Comparación entre talentos**")
    evaluados = analitica.evaluados(filtrado)
    por_id = {int(fila["id_talento"]): fila for _, fila in evaluados.iterrows()}
    elegidos = st.multiselect(
        f"Seleccione hasta {analitica.MAX_RADAR} talentos", list(por_id), max_selections=analitica.MAX_RADAR,
        placeholder="Seleccione talentos",
        format_func=lambda id_talento: f"{id_talento} - {por_id[id_talento]['nombre']}")
    if elegidos:
        st.plotly_chart(graficas.radar([(por_id[id_talento]["nombre"], analitica.valores_radar(por_id[id_talento]))
                                        for id_talento in elegidos]), key="radar")
    explicar("Comparación entre talentos")
