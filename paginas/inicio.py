import streamlit as st

from backend import permisos, sesion
from backend.interfaz import NOMBRE

usuario = sesion.usuario_actual()

st.title("Inicio")
st.write(f"Bienvenido(a) a {NOMBRE}, **{usuario['nombre']}**.")
st.caption(f"{permisos.NOMBRES_CARGO[usuario['cargo']]} · {usuario['area']}")
st.info("Use el menú de la izquierda para ir a cada sección. Si tiene dudas, consulte los manuales en "
        "Ayuda > Soporte.")
