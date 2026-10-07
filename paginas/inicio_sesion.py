import streamlit as st

from backend import alertas, auth, errores, ia, permisos, sesion
from backend.interfaz import DESCRIPCION, LOGO, NOMBRE, SIGNIFICADO

st.image(LOGO, width=320)
st.caption(f"{SIGNIFICADO} · {DESCRIPCION}")

if st.session_state.pop("sesion_expirada", False):
    st.warning(errores.CATALOGO["E-303"])

with st.form("inicio_sesion"):
    usuario = st.text_input("Usuario")
    contrasena = st.text_input("Contraseña", type="password")
    enviar = st.form_submit_button("Iniciar sesión", type="primary")

# Zona de mensajes para E-301/E-302
if enviar:
    if not usuario.strip() or not contrasena:
        st.error("Escriba su usuario y contraseña.")
    else:
        try:
            datos = auth.iniciar_sesion(usuario.strip(), contrasena)
        except errores.ErrorSistema as error:
            if error.codigo not in ("E-301", "E-302"):
                raise
            st.error(error.mensaje)
        else:
            sesion.iniciar(datos)
            # Alertas de "días sin evaluar" (PRD, 12.3): Streamlit no tiene tareas programadas
            alertas.revisar_sin_evaluar()
            if permisos.puede(datos, "evaluar_ia"):
                # La primera carga del modelo tarda más que el tiempo máximo (PRD, 10)
                ia.precargar()
            st.rerun()

with st.expander("¿Olvidaste tu usuario o contraseña?"):
    with st.form("restablecer_acceso", clear_on_submit=True):
        correo = st.text_input("Correo registrado")
        if st.form_submit_button("Enviar solicitud") and correo.strip():
            auth.solicitar_restablecimiento(correo.strip())
            st.success("Si el correo está registrado, el Administrador de RH se pondrá en contacto.")
