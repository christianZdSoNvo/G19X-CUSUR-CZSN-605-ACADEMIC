import pandas as pd
import streamlit as st

from backend import analitica, catalogos, errores, graficas, permisos, reportes, sesion, talentos, vistas

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "reportes")
area_fija = permisos.area_permitida(usuario)


def nombre_nivel(nivel):
    return graficas.NOMBRE_NIVEL[nivel]


def exportacion(clave, obtener_datos):
    # Botones "Generar PDF" y "Generar Excel"; el archivo generado se guarda en la sesión
    # para ofrecer su descarga. La clave identifica el talento o los filtros, así que al
    # cambiarlos ya no se ofrece el archivo anterior.
    columnas = st.columns(2)
    for columna, formato, etiqueta, icono in ((columnas[0], "pdf", "Generar PDF", ":material/picture_as_pdf:"),
                                              (columnas[1], "excel", "Generar Excel", ":material/table_view:")):
        if columna.button(etiqueta, key=f"{clave}_{formato}", icon=icono, width="stretch"):
            with st.spinner("Generando el reporte..."):
                st.session_state["reporte_generado"] = {"clave": clave,
                                                        **reportes.exportar(usuario, obtener_datos(), formato)}
    generado = st.session_state.get("reporte_generado")
    if not generado or generado["clave"] != clave:
        return
    if generado["codigo"]:
        st.warning(f"{errores.CATALOGO[generado['codigo']]} (código {generado['codigo']})")
    else:
        st.success(f"Reporte generado: {generado['archivo']}")
    st.download_button(f"Descargar {generado['archivo']}", generado["contenido"], file_name=generado["archivo"],
                       mime=generado["mime"], type="primary", icon=":material/download:", on_click="ignore",
                       key=f"{clave}_descarga")


def filtro_area(columna, clave):
    if area_fija:
        columna.text_input("Área", area_fija, disabled=True, key=f"{clave}_fija")
        return area_fija
    return columna.selectbox("Área", catalogos.AREAS, index=None, placeholder="Todas las áreas", key=clave)


# --- Reporte individual: buscador por ID o nombre y lista general (PRD, 6.4 y 13.2) ---

def reporte_individual():
    texto_col, area_col = st.columns([2, 1])
    texto = texto_col.text_input("Buscar por ID o nombre", key="rep_texto")
    area = filtro_area(area_col, "rep_area")

    resultados = talentos.buscar(usuario, texto, area)
    if not resultados:
        if texto.strip():
            st.warning(talentos.NO_IDENTIFICADO)
        else:
            st.info("No hay talentos registrados" + (f" en {area}." if area else "."))
        return

    ultimas = analitica.talentos_con_ultima_evaluacion(usuario).set_index("id_talento")
    tabla = st.dataframe(pd.DataFrame([{
        "ID": fila["id_talento"],
        "Nombre": fila["nombre"],
        "Área": fila["area"],
        "Correo": fila["correo"],
        "Potencial": (nombre_nivel(ultimas.at[fila["id_talento"], "potencial_crecimiento_nivel"])
                      if fila["id_talento"] in ultimas.index
                      and not pd.isna(ultimas.at[fila["id_talento"], "id_evaluacion"]) else reportes.SIN_EVALUACION),
        "Última evaluación": (vistas.fecha(ultimas.at[fila["id_talento"], "fecha_evaluacion"])
                              if fila["id_talento"] in ultimas.index
                              and not pd.isna(ultimas.at[fila["id_talento"], "id_evaluacion"]) else ""),
    } for fila in resultados]), hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key="rep_lista")
    st.caption(f"{len(resultados)} talento(s). Seleccione un renglón para generar su reporte.")
    if not tabla.selection.rows:
        return

    elegido = resultados[tabla.selection.rows[0]]
    st.subheader(elegido["nombre"])
    st.caption(f"ID {elegido['id_talento']} · {elegido['area']} · Ingreso: {vistas.fecha(elegido['fecha_ingreso'])}")
    exportacion(f"individual_{elegido['id_talento']}",
                lambda: reportes.datos_individual(usuario, elegido["id_talento"]))


# --- Reporte general: mismos filtros que los paneles (PRD, 6.4) ---

def reporte_general():
    fila1 = st.columns(2)
    area = filtro_area(fila1[0], "rep_general_area")
    niveles = fila1[1].multiselect("Nivel de potencial", analitica.NIVELES, format_func=nombre_nivel,
                                   placeholder="Todos", key="rep_general_niveles")
    fila2 = st.columns(2)
    clasificaciones = fila2[0].multiselect("Clasificación 9-box", analitica.CLASIFICACIONES, placeholder="Todas",
                                           key="rep_general_9box")
    fechas = fila2[1].date_input("Fechas de evaluación", value=(), format="DD/MM/YYYY", key="rep_general_fechas")
    fechas = tuple(fechas) if len(fechas) == 2 else None
    st.caption("Sin filtro de fechas, las \"evaluaciones del periodo\" son las del mes en curso.")

    datos = reportes.datos_general(usuario, area=area, niveles=niveles, clasificaciones=clasificaciones, fechas=fechas)
    indicadores = datos["indicadores"]
    if not indicadores["total"]:
        st.warning("Ningún talento cumple con los filtros seleccionados.")
        return
    tarjetas = st.columns(4)
    tarjetas[0].metric("Talentos", indicadores["total"])
    alto = indicadores["porcentajes"]["alto"]
    tarjetas[1].metric("Con potencial alto", "Sin evaluaciones" if alto is None else f"{alto} %")
    tarjetas[2].metric("Evaluaciones del periodo", indicadores["evaluaciones_periodo"])
    tarjetas[3].metric("Sin evaluación", indicadores["sin_evaluar"])
    exportacion(f"general_{area}_{sorted(niveles)}_{sorted(clasificaciones)}_{fechas}", lambda: datos)


st.title("Reportes")
individual, general = st.tabs(["Reporte individual", "Reporte general"])
with individual:
    reporte_individual()
with general:
    reporte_general()
