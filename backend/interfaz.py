import streamlit as st

from backend import auth, errores, seguridad


def pantalla_error(codigo):
    # Pantalla de error del PRD, sección 7: mensaje, código para copiar y "Reiniciar"
    st.session_state["ultimo_codigo_error"] = codigo
    st.error(errores.CATALOGO[codigo])
    st.caption("Código de error (use el ícono de la derecha para copiarlo):")
    st.code(codigo, language=None)
    if codigo == "E-304":
        # Reiniciar volvería a la misma sección; se regresa al inicio
        if st.button("Volver al inicio", type="primary"):
            st.switch_page("paginas/inicio.py")
    elif st.button("Reiniciar", type="primary"):
        st.rerun()
    st.stop()


def ocultar_barra_lateral():
    # Antes de entrar al sistema (login o cambio obligatorio) no debe poder abrirse
    # la barra lateral; Streamlit muestra su botón aunque esté vacía
    st.html("<style>[data-testid='stSidebar'], [data-testid='stExpandSidebarButton'], "
            "[data-testid='stSidebarCollapseButton'] {display: none;}</style>")


def en_construccion(titulo, fase):
    st.title(titulo)
    st.info(f"Esta sección se implementará en la fase {fase}.")


def formulario_contrasena(id_usuario, pedir_actual):
    # Formulario común del cambio obligatorio y del voluntario (Configuración).
    # Devuelve True si la contraseña se cambió.
    st.info(seguridad.REQUISITOS)
    with st.form("cambio_contrasena", clear_on_submit=True):
        actual = st.text_input("Contraseña actual", type="password") if pedir_actual else None
        nueva = st.text_input("Contraseña nueva", type="password")
        confirmar = st.text_input("Confirmar contraseña", type="password")
        guardar = st.form_submit_button("Guardar", type="primary")

    if not guardar:
        return False
    if pedir_actual and not actual:
        problemas = ["Escriba su contraseña actual."]
    elif nueva != confirmar:
        problemas = ["Las contraseñas no coinciden."]
    else:
        problemas = auth.cambiar_contrasena(id_usuario, nueva, actual)
    for problema in problemas:
        st.error(problema)
    return not problemas
