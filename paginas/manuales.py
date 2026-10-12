import streamlit as st

from backend import errores, manuales, permisos, sesion, vistas

# Ambos roles consultan; solo el Administrador edita ("editar_manuales"). Cada manual
# va dirigido a un cargo: el Encargado solo ve los suyos; el Administrador ve los suyos
# y puede consultar, crear y editar también los del Encargado.
usuario = sesion.usuario_actual()
permisos.exigir(usuario, "consultar_manuales")

st.title("Manuales")

if not permisos.puede(usuario, "editar_manuales"):
    vistas.consulta_manuales(usuario, "manuales")
    st.stop()


def elegir_cargo(clave, etiqueta):
    return st.radio(etiqueta, manuales.CARGOS, format_func=permisos.NOMBRES_CARGO.get,
                    horizontal=True, key=clave)


def formulario(clave, cargo, manual=None):
    # Devuelve (datos, imágenes nuevas, id_imagen a quitar) si se pulsó "Guardar"; si no, None.
    # Las secciones son las del menú del cargo al que va dirigido el manual.
    manual = manual or {}
    problemas = st.session_state.get(f"problemas_{clave}", {})
    secciones = manuales.secciones_de(cargo)
    with st.form(clave):
        seccion = st.selectbox("Sección del sistema", secciones, placeholder="Seleccione una sección",
                               index=secciones.index(manual["seccion_software"]) if manual else None)
        if "seccion_software" in problemas:
            st.error(problemas["seccion_software"])
        texto = st.text_area("Texto", manual.get("contenido_texto") or "", height=180)
        if "contenido_texto" in problemas:
            st.error(problemas["contenido_texto"])
        # Imágenes actuales en el orden en que se muestran; cada una se puede quitar
        quitar = []
        actuales = manual.get("imagenes", [])
        if actuales:
            st.markdown("**Imágenes actuales**")
            columnas = st.columns(3)
            for numero, imagen in enumerate(actuales, start=1):
                with columnas[(numero - 1) % 3]:
                    st.image(bytes(imagen["imagen"]), caption=f"Imagen {numero}", width="stretch")
                    if st.checkbox("Quitar", key=f"{clave}_quitar_{imagen['id_imagen']}"):
                        quitar.append(imagen["id_imagen"])
        nuevas = st.file_uploader(
            ("Agregar imágenes" if actuales else "Imágenes") + f" (PNG o JPG, máximo 5 MB cada una; hasta "
            f"{manuales.MAX_IMAGENES} por manual)", type=["png", "jpg", "jpeg"], accept_multiple_files=True,
            max_upload_size=manuales.MAX_IMAGEN_MB)
        st.caption("Se muestran debajo del texto en el orden en que se eligen"
                   + ("; las nuevas van después de las actuales." if actuales else "."))
        if "imagen" in problemas:
            st.error(problemas["imagen"])
            st.caption("Código de error: E-402")
        if "imagenes" in problemas:
            st.error(problemas["imagenes"])
        enlace = st.text_input("Enlace (opcional)", manual.get("contenido_enlace") or "",
                               max_chars=manuales.MAX_ENLACE, placeholder="https://...")
        if "contenido_enlace" in problemas:
            st.error(problemas["contenido_enlace"])
        if st.form_submit_button("Guardar", type="primary"):
            datos = {"dirigido_a": cargo, "seccion_software": seccion, "contenido_texto": texto, "contenido_enlace": enlace}
            return datos, [archivo.getvalue() for archivo in nuevas or []], quitar
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
        # Con otra clave, los formularios quedan sin los archivos elegidos después de guardar
        st.session_state["version_manuales"] = st.session_state.get("version_manuales", 0) + 1
    st.rerun()


aviso = st.session_state.pop("aviso_manuales", None)
if aviso:
    st.success(aviso)

consultar, nuevo, editar = st.tabs(["Consultar", "Nuevo manual", "Editar o eliminar"])

with consultar:
    vistas.consulta_manuales(usuario, "manuales", elegir_cargo=True)

with nuevo:
    # Fuera del formulario, para que la lista de secciones cambie al elegir el cargo
    cargo_nuevo = elegir_cargo("cargo_nuevo_manual", "Dirigido a")
    clave_nuevo = f"nuevo_manual_{cargo_nuevo}_{st.session_state.get('version_manuales', 0)}"
    capturado = formulario(clave_nuevo, cargo_nuevo)
    if capturado:
        datos, imagenes, _ = capturado
        guardar(clave_nuevo, lambda: manuales.crear(usuario, datos, imagenes)[0], "Manual agregado.")

with editar:
    cargo_editar = elegir_cargo("cargo_editar_manual", "Manuales de")
    todos = manuales.listar(usuario, dirigido_a=cargo_editar)
    if not todos:
        st.info(f"No hay manuales para el {permisos.NOMBRES_CARGO[cargo_editar]}.")
    else:
        por_id = {manual["id_manual"]: manual for manual in todos}
        id_manual = st.selectbox(
            "Manual", list(por_id), index=None, placeholder="Seleccione un manual",
            format_func=lambda i: f"{por_id[i]['seccion_software']} · "
                                  f"{(por_id[i]['contenido_texto'] or '(sin texto)')[:60]}",
        )
        if id_manual is not None:
            clave = f"editar_manual_{id_manual}_{st.session_state.get('version_manuales', 0)}"
            capturado = formulario(clave, cargo_editar, por_id[id_manual])
            if capturado:
                datos, imagenes, quitar = capturado
                guardar(clave, lambda: manuales.editar(usuario, id_manual, datos, imagenes, quitar),
                        "Manual actualizado.")

            st.divider()
            st.markdown("**Eliminar manual**")
            confirmar = st.checkbox("Confirmo que deseo eliminar este manual.", key=f"confirmar_{clave}")
            if st.button("Eliminar", disabled=not confirmar, key=f"eliminar_{clave}"):
                manuales.eliminar(usuario, id_manual)
                st.session_state["aviso_manuales"] = "Manual eliminado."
                st.rerun()
