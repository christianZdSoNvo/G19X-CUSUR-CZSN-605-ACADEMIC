import streamlit as st

from backend import auth, seguridad, sesion

usuario = sesion.usuario_actual()

st.title("Cambio de contraseña")
st.write(f"Hola, {usuario['nombre']}. Antes de continuar debe escribir una contraseña nueva.")
st.info(seguridad.REQUISITOS)

with st.form("cambio_obligatorio"):
    nueva = st.text_input("Contraseña nueva", type="password")
    confirmar = st.text_input("Confirmar contraseña", type="password")
    guardar = st.form_submit_button("Guardar", type="primary")

if guardar:
    if nueva != confirmar:
        problemas = ["Las contraseñas no coinciden."]
    else:
        problemas = auth.cambiar_contrasena(usuario["id_usuario"], nueva)
    if problemas:
        for problema in problemas:
            st.error(problema)
    else:
        usuario["debe_cambiar_contrasena"] = False
        st.rerun()

if st.button("Cerrar sesión"):
    sesion.cerrar()
    st.rerun()
