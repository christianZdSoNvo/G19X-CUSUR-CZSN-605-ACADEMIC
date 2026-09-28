import streamlit as st

from backend import errores


def pantalla_error(codigo):
    # Pantalla de error del PRD, sección 7: mensaje, código para copiar y "Reiniciar"
    st.session_state["ultimo_codigo_error"] = codigo
    st.error(errores.CATALOGO[codigo])
    st.caption("Código de error (use el ícono de la derecha para copiarlo):")
    st.code(codigo, language=None)
    if st.button("Reiniciar", type="primary"):
        st.rerun()
    st.stop()
