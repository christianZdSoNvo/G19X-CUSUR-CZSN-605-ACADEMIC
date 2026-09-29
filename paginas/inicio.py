import streamlit as st

from backend import permisos, sesion

usuario = sesion.usuario_actual()

st.title("Inicio")
st.write(f"Bienvenido(a), **{usuario['nombre']}**.")
st.caption(f"{permisos.NOMBRES_CARGO[usuario['cargo']]} · {usuario['area']}")
st.info("Las secciones del sistema se agregarán en las siguientes fases.")
