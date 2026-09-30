"""Punto de entrada del sistema: streamlit run app.py"""

import streamlit as st

from backend import errores, menu, permisos, sesion
from backend.interfaz import NOMBRE, SIGNIFICADO, ocultar_barra_lateral, pantalla_error

st.set_page_config(page_title=NOMBRE, layout="centered")


def dentro_del_sistema(usuario):
    # Sesión iniciada y sin cambio obligatorio de contraseña pendiente
    return usuario is not None and not usuario["debe_cambiar_contrasena"]


try:
    sesion.revisar_inactividad()
    usuario = sesion.usuario_actual()

    if usuario is None:
        paginas = [st.Page("paginas/inicio_sesion.py", title="Iniciar sesión")]
    elif usuario["debe_cambiar_contrasena"]:
        paginas = [st.Page("paginas/cambiar_contrasena.py", title="Cambiar contraseña")]
    else:
        paginas = {}
        for seccion, archivo, titulo, icono, visible in menu.opciones(usuario):
            paginas.setdefault(seccion, []).append(st.Page(
                archivo, title=titulo, icon=icono, default=archivo == "paginas/inicio.py",
                visibility="visible" if visible else "hidden",
            ))
        with st.sidebar:
            st.markdown(f"## {NOMBRE}")
            st.caption(SIGNIFICADO)
            st.divider()
            st.write(f"**{usuario['nombre']}**")
            st.caption(f"{permisos.NOMBRES_CARGO[usuario['cargo']]} · {usuario['area']}")
            if st.button("Cerrar sesión"):
                sesion.cerrar()
                st.rerun()

    # Sin sesión o con cambio obligatorio no se muestran el menú ni la barra lateral
    if not dentro_del_sistema(usuario):
        ocultar_barra_lateral()
    st.navigation(paginas, position="sidebar" if dentro_del_sistema(usuario) else "hidden").run()
except errores.ErrorSistema as error:
    if not dentro_del_sistema(sesion.usuario_actual()):
        ocultar_barra_lateral()
    pantalla_error(error.codigo)
