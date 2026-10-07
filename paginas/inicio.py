import streamlit as st

from backend import menu, notificaciones, permisos, sesion
from backend.interfaz import NOMBRE

usuario = sesion.usuario_actual()

st.title("Inicio")
st.write(f"Bienvenido(a) a {NOMBRE}, **{usuario['nombre']}**.")
st.caption(f"{permisos.NOMBRES_CARGO[usuario['cargo']]} · {usuario['area']}")

pendientes = notificaciones.pendientes(usuario)
if pendientes:
    st.warning(f"Tiene {pendientes} notificación(es) pendiente(s) en Notificaciones y alertas.",
               icon=":material/notifications_active:")

# Las mismas secciones del menú de la izquierda, solo las que el rol puede usar;
# Notificaciones lleva el número de pendientes igual que en el menú
for seccion, opciones in menu.accesos(usuario, pendientes).items():
    st.markdown(f"**{seccion}**")
    columnas = st.columns(3)
    for indice, (archivo, titulo, icono) in enumerate(opciones):
        with columnas[indice % 3].container(border=True):
            st.page_link(archivo, label=titulo, icon=icono, width="stretch")

st.caption("Si tiene dudas, consulte los manuales en Ayuda > Soporte.")
