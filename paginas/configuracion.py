import streamlit as st

from backend import permisos, sesion
from backend.interfaz import formulario_contrasena

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "configuracion_general")

st.title("Configuración")

# El tema claro/oscuro y el contacto de soporte se agregan en la fase 7
st.subheader("Cambiar contraseña")
if st.session_state.pop("contrasena_cambiada", False):
    st.success("Contraseña actualizada.")
if formulario_contrasena(usuario["id_usuario"], pedir_actual=True):
    st.session_state["contrasena_cambiada"] = True
    st.rerun()

st.subheader("Sesión")
if st.button("Cerrar sesión", key="cerrar_sesion_configuracion"):
    sesion.cerrar()
    st.rerun()
