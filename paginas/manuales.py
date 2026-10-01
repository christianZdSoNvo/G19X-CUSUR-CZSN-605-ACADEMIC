import streamlit as st

from backend import errores, manuales, permisos, sesion, vistas

# Ambos roles consultan; solo el Administrador edita ("editar_manuales"). El Encargado
# solo ve los manuales de las secciones que tiene en su menú.
usuario = sesion.usuario_actual()
permisos.exigir(usuario, "consultar_manuales")

st.title("Manuales")

if not permisos.puede(usuario, "editar_manuales"):
    vistas.consulta_manuales(usuario, "manuales")
    st.stop()


def formulario(clave, manual=None):
    # Devuelve (datos, imagen, quitar_imagen) si se pulsó "Guardar"; si no, None
    manual = manual or {}
    problemas = st.session_state.get(f"problemas_{clave}", {})
    secciones = list(manuales.SECCIONES)
    with st.form(clave):
        seccion = st.selectbox("Sección del sistema", secciones, placeholder="Seleccione una sección",
                               index=secciones.index(manual["seccion_software"]) if manual else None)
        if "seccion_software" in problemas:
            st.error(problemas["seccion_software"])
        texto = st.text_area("Texto", manual.get("contenido_texto") or "", height=180)
        if "contenido_texto" in problemas:
            st.error(problemas["contenido_texto"])
        imagen = st.file_uploader("Imagen (PNG o JPG, máximo 5 MB)", type=["png", "jpg", "jpeg"])
        quitar = False
        if manual.get("contenido_imagen"):
            st.image(bytes(manual["contenido_imagen"]), caption="Imagen actual", width=300)
            quitar = st.checkbox("Quitar la imagen actual")
        if "imagen" in problemas:
            st.error(problemas["imagen"])
            st.caption("Código de error: E-402")
        enlace = st.text_input("Enlace (opcional)", manual.get("contenido_enlace") or "",
                               max_chars=manuales.MAX_ENLACE, placeholder="https://...")
        if "contenido_enlace" in problemas:
            st.error(problemas["contenido_enlace"])
        if st.form_submit_button("Guardar", type="primary"):
            datos = {"seccion_software": seccion, "contenido_texto": texto, "contenido_enlace": enlace}
            return datos, imagen.getvalue() if imagen else None, quitar
    return None


def guardar(clave, accion, aviso):
    # Los errores de captura y E-402 se muestran debajo de su campo; los demás
    # pasan a la pantalla de error general
    try:
        problemas = accion()
    except errores.ErrorSistema as error:
        if error.codigo != "E-402":
            raise
        problemas = {"imagen": error.mensaje}
    st.session_state[f"problemas_{clave}"] = problemas
    if not problemas:
        st.session_state["aviso_manuales"] = aviso
        # Un formulario nuevo (otra clave) queda vacío después de guardar
        st.session_state["version_nuevo_manual"] = st.session_state.get("version_nuevo_manual", 0) + 1
    st.rerun()


aviso = st.session_state.pop("aviso_manuales", None)
if aviso:
    st.success(aviso)

consultar, nuevo, editar = st.tabs(["Consultar", "Nuevo manual", "Editar o eliminar"])

with consultar:
    vistas.consulta_manuales(usuario, "manuales")

with nuevo:
    clave_nuevo = f"nuevo_manual_{st.session_state.get('version_nuevo_manual', 0)}"
    capturado = formulario(clave_nuevo)
    if capturado:
        datos, imagen, _ = capturado
        guardar(clave_nuevo, lambda: manuales.crear(usuario, datos, imagen)[0], "Manual agregado.")

with editar:
    todos = manuales.listar(usuario)
    if not todos:
        st.info("No hay manuales registrados.")
    else:
        por_id = {manual["id_manual"]: manual for manual in todos}
        id_manual = st.selectbox(
            "Manual", list(por_id), index=None, placeholder="Seleccione un manual",
            format_func=lambda i: f"{por_id[i]['seccion_software']} · "
                                  f"{(por_id[i]['contenido_texto'] or '(sin texto)')[:60]}",
        )
        if id_manual is not None:
            clave = f"editar_manual_{id_manual}"
            capturado = formulario(clave, por_id[id_manual])
            if capturado:
                datos, imagen, quitar = capturado
                guardar(clave, lambda: manuales.editar(usuario, id_manual, datos, imagen, quitar),
                        "Manual actualizado.")

            st.divider()
            st.markdown("**Eliminar manual**")
            confirmar = st.checkbox("Confirmo que deseo eliminar este manual.", key=f"confirmar_{clave}")
            if st.button("Eliminar", disabled=not confirmar, key=f"eliminar_{clave}"):
                manuales.eliminar(usuario, id_manual)
                st.session_state["aviso_manuales"] = "Manual eliminado."
                st.rerun()
