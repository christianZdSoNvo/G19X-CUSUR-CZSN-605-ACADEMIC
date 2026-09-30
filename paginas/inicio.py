import streamlit as st

from backend import permisos, sesion
from backend.interfaz import NOMBRE

usuario = sesion.usuario_actual()

st.title("Inicio")
st.write(f"Bienvenido(a) a {NOMBRE}, **{usuario['nombre']}**.")
st.caption(f"{permisos.NOMBRES_CARGO[usuario['cargo']]} · {usuario['area']}")
st.info("Las secciones del sistema se agregarán en las siguientes fases.")
