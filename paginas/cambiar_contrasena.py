import streamlit as st

from backend import sesion
from backend.interfaz import formulario_contrasena

usuario = sesion.usuario_actual()

st.title("Cambio de contraseña")
st.write(f"Hola, {usuario['nombre']}. Antes de continuar debe escribir una contraseña nueva.")

if formulario_contrasena(usuario["id_usuario"], pedir_actual=False):
    usuario["debe_cambiar_contrasena"] = False
    st.rerun()

if st.button("Cerrar sesión"):
    sesion.cerrar()
    st.rerun()
