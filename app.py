"""Punto de entrada del sistema: streamlit run app.py

Fase 0: página de verificación del entorno (MySQL y Ollama).
"""

import streamlit as st

from backend import config, db, ia

st.set_page_config(page_title="Sistema de Talento", layout="centered")

st.title("Sistema de Identificación de Talento de Alto Potencial")
st.caption("Fase 0 · Verificación del entorno")

st.subheader("MySQL")
try:
    version, existe = db.probar_conexion()
    st.success(f"Conexión correcta con MySQL {version}.")
    if existe:
        st.info(f"La base de datos `{config.DB_NAME}` ya existe.")
    else:
        st.warning(f"La base de datos `{config.DB_NAME}` todavía no existe (se crea en la fase 1).")
except Exception as error:
    st.error(f"No fue posible conectar con MySQL: {error}")

st.subheader("Ollama")
try:
    modelos, disponible = ia.probar_conexion()
    st.success(f"Conexión correcta con Ollama en {config.OLLAMA_HOST}.")
    if disponible:
        st.info(f"El modelo `{config.OLLAMA_MODEL}` está descargado.")
    else:
        st.warning(
            f"El modelo `{config.OLLAMA_MODEL}` no está descargado. "
            f"Modelos instalados: {', '.join(modelos) or 'ninguno'}."
        )
except Exception as error:
    st.error(f"No fue posible conectar con Ollama: {error}")
