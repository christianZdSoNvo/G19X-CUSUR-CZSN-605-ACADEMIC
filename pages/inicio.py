import streamlit as st

from backend import sesion

usuario = sesion.usuario_actual()

st.title("Inicio")
st.write(f"Bienvenido(a), **{usuario['nombre']}**.")
st.caption(f"{usuario['cargo']} · {usuario['area']}")
st.info("Las secciones del sistema se agregarán en las siguientes fases.")
