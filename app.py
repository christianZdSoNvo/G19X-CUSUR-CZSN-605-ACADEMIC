"""Punto de entrada del sistema: streamlit run app.py"""

import streamlit as st

from backend import errores, menu, notificaciones, permisos, sesion, vistas
from backend.interfaz import ICONO, LOGO, NOMBRE, SIGNIFICADO, ocultar_barra_lateral, pantalla_error

st.set_page_config(page_title=NOMBRE, page_icon=ICONO, layout="centered")


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
        enlaces = {}
        pendientes = notificaciones.pendientes(usuario)
        for seccion, archivo, titulo, icono, visible in menu.opciones(usuario, pendientes):
            pagina = st.Page(archivo, title=titulo, icon=icono, default=archivo == "paginas/inicio.py")
            paginas.setdefault(seccion, []).append(pagina)
            if visible:
                enlaces.setdefault(seccion, []).append((archivo, pagina))

    # Todas las páginas se registran, pero el menú de Streamlit queda oculto: el menú se
    # dibuja con enlaces para poner la selección de paneles debajo de "Paneles analíticos"
    actual = st.navigation(paginas, position="hidden")
    if dentro_del_sistema(usuario):
        # Logo arriba a la izquierda de la barra lateral; con la barra cerrada, arriba
        # a la izquierda de la pantalla de contenido
        st.logo(LOGO, size="large")
        with st.sidebar:
            for seccion, lista in enlaces.items():
                if seccion:
                    st.caption(f"**{seccion}**")
                for archivo, pagina in lista:
                    st.page_link(pagina, width="stretch")
                    if archivo == menu.PANELES_ANALITICOS and actual.url_path == pagina.url_path:
                        st.pills("Paneles a mostrar", list(menu.PANELES), selection_mode="multi",
                                 key=menu.CLAVE_PANELES, help="Sin elegir ninguno se muestran todos.")
            st.divider()
            st.caption(SIGNIFICADO)
            foto, datos = st.columns([1, 3], vertical_alignment="center")
            with foto:
                vistas.foto_perfil(sesion.foto_usuario(), ancho=48)
            datos.write(f"**{usuario['nombre']}**")
            datos.caption(f"{permisos.NOMBRES_CARGO[usuario['cargo']]} · {usuario['area']}")
            if st.button("Cerrar sesión"):
                sesion.cerrar()
                st.rerun()
    else:
        # Sin sesión o con cambio obligatorio no se muestran el menú ni la barra lateral
        ocultar_barra_lateral()
    actual.run()
except errores.ErrorSistema as error:
    if not dentro_del_sistema(sesion.usuario_actual()):
        ocultar_barra_lateral()
    pantalla_error(error.codigo)
