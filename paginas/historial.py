import streamlit as st

from backend import catalogos, permisos, sesion, talentos, vistas

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "historial")

st.title("Historial y evolución")

# Buscador por ID o nombre (PRD, 13.3); el Encargado solo ve su área
texto_col, area_col = st.columns([2, 1])
texto = texto_col.text_input("Buscar por ID o nombre")
area_fija = permisos.area_permitida(usuario)
if area_fija:
    area_col.text_input("Área", area_fija, disabled=True)
    area = area_fija
else:
    area = area_col.selectbox("Área", catalogos.AREAS, index=None, placeholder="Todas las áreas")

resultados = talentos.buscar(usuario, texto, area)
if not resultados:
    if texto.strip():
        st.warning(talentos.NO_IDENTIFICADO)
    else:
        st.info("No hay talentos registrados" + (f" en {area}." if area else "."))
    st.stop()

por_id = {fila["id_talento"]: fila for fila in resultados}
# Un talento elegido desde el drill-down de paneles llega ya seleccionado
preseleccion = st.session_state.pop("historial_talento", None)
if preseleccion in por_id:
    st.session_state["historial_elegido"] = preseleccion
id_elegido = st.selectbox(
    "Talento", list(por_id), index=None, placeholder="Seleccione un talento", key="historial_elegido",
    format_func=lambda id_talento: f"{id_talento} - {por_id[id_talento]['nombre']}")
if id_elegido is None:
    st.stop()

talento = talentos.obtener(usuario, id_elegido)
st.subheader(talento["nombre"])
st.caption(f"{talento['area']} · Ingreso: {vistas.fecha(talento['fecha_ingreso'])}")
vistas.historial_talento(usuario, talento, "historial")
