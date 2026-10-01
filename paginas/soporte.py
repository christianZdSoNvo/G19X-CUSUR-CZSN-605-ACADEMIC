import streamlit as st

from backend import permisos, sesion, vistas

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "soporte")

# Soporte (PRD, 13.6): pestañas "Manuales" y "Contacto"
st.title("Soporte")
manuales, contacto = st.tabs(["Manuales", "Contacto"])
with manuales:
    vistas.consulta_manuales(usuario, "soporte")
with contacto:
    st.caption("Si apareció un código de error, inclúyalo en el mensaje.")
    vistas.contacto_soporte("soporte")
