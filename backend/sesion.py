import time

import streamlit as st

from backend import auth

# Datos de la sesión en st.session_state (PRD, 12.2)


def iniciar(usuario):
    st.session_state["usuario"] = usuario
    st.session_state["ultimo_acceso"] = time.time()


def usuario_actual():
    return st.session_state.get("usuario")


def revisar_inactividad():
    # Streamlit solo ejecuta código cuando el usuario interactúa, así que la
    # inactividad se revisa en cada interacción
    usuario = usuario_actual()
    if usuario is None:
        return
    if time.time() - st.session_state["ultimo_acceso"] > usuario["minutos_inactividad"] * 60:
        cerrar("inactividad")
        st.session_state["sesion_expirada"] = True
    else:
        st.session_state["ultimo_acceso"] = time.time()


def cerrar(motivo="manual"):
    usuario = usuario_actual()
    st.session_state.clear()
    if usuario is not None:
        auth.registrar_cierre(usuario["id_usuario"], motivo)
