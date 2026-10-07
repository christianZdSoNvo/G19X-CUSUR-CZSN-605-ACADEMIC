import streamlit as st

from backend import permisos, sesion, usuarios, vistas
from backend.interfaz import TEMAS, aplicar_tema, formulario_contrasena

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "configuracion_general")

st.title("Configuración")

# Configuración general (PRD, 13.4): foto de perfil, contraseña, tema, contacto de soporte
# y cerrar sesión
st.subheader("Foto de perfil")
aviso = st.session_state.pop("aviso_foto", None)
if aviso:
    st.success(aviso)
foto, editor = st.columns([1, 3])
with foto:
    vistas.foto_perfil(sesion.foto_usuario())
with editor:
    aviso = vistas.editor_foto("foto_usuario", sesion.foto_usuario(),
                               lambda nueva: sesion.guardar_foto(usuarios.cambiar_foto(usuario, nueva)))
if aviso:
    st.session_state["aviso_foto"] = aviso
    st.rerun()

st.subheader("Cambiar contraseña")
if st.session_state.pop("contrasena_cambiada", False):
    st.success("Contraseña actualizada.")
if formulario_contrasena(usuario["id_usuario"], pedir_actual=True):
    st.session_state["contrasena_cambiada"] = True
    st.rerun()

st.subheader("Tema")


def cambiar_tema():
    # El script solo se agrega en la ejecución siguiente al cambio, no en cada recarga
    st.session_state["tema_elegido"] = st.session_state["tema"]
    st.session_state["tema_pendiente"] = True


# Sin elección previa en la sesión se muestra el tema que el navegador tiene activo
actual = st.session_state.get("tema_elegido") or ("Oscuro" if st.context.theme.type == "dark" else "Claro")
st.radio("Apariencia", list(TEMAS), index=list(TEMAS).index(actual), horizontal=True, key="tema",
         on_change=cambiar_tema)
st.caption("La elección se guarda en este navegador.")
if st.session_state.pop("tema_pendiente", False):
    aplicar_tema(st.session_state["tema_elegido"])

st.subheader("Contacto de soporte")
vistas.contacto_soporte("configuracion")

st.subheader("Sesión")
if st.button("Cerrar sesión", key="cerrar_sesion_configuracion"):
    sesion.cerrar()
    st.rerun()
