import pandas as pd
import streamlit as st

from backend import catalogos, errores, permisos, sesion, usuarios

administrador = sesion.usuario_actual()
permisos.exigir(administrador, "gestion_usuarios")


def formulario(clave, datos=None):
    # Devuelve los datos capturados si se pulsó "Guardar"; si no, None
    datos = datos or {}
    with st.form(clave, clear_on_submit=datos == {}):
        izquierda, derecha = st.columns(2)
        with izquierda:
            nombre = st.text_input("Nombre completo", datos.get("nombre", ""), max_chars=50)
            usuario = st.text_input("Usuario", datos.get("usuario", ""), max_chars=30)
            correo = st.text_input("Correo", datos.get("correo", ""), max_chars=70)
        with derecha:
            tel_mx = st.text_input("Teléfono (10 dígitos)", datos.get("tel_mx", ""), max_chars=10)
            cargo = st.selectbox("Cargo", usuarios.CARGOS, format_func=permisos.NOMBRES_CARGO.get,
                                 index=usuarios.CARGOS.index(datos.get("cargo", permisos.ENCARGADO)))
            area = st.selectbox("Área", catalogos.AREAS,
                                index=catalogos.AREAS.index(datos["area"]) if "area" in datos else None,
                                placeholder="Seleccione un área")
        if st.form_submit_button("Guardar", type="primary"):
            return {"nombre": nombre, "usuario": usuario, "correo": correo,
                    "tel_mx": tel_mx, "cargo": cargo, "area": area}
    return None


def guardar(accion):
    # Ejecuta la acción; los errores de captura (E-003/E-004) se muestran en la misma
    # pantalla y los demás pasan a la pantalla de error general
    try:
        problemas = accion()
    except errores.ErrorSistema as error:
        if error.codigo not in ("E-003", "E-004"):
            raise
        problemas = [error.mensaje]
    for problema in problemas:
        st.error(problema)
    return not problemas


def avisar(texto, temporal=None):
    # El aviso se muestra después de recargar, para que la lista ya incluya el cambio
    st.session_state["aviso_usuarios"] = (texto, temporal)
    st.rerun()


st.title("Gestión de usuarios")

aviso = st.session_state.pop("aviso_usuarios", None)
if aviso:
    texto, temporal = aviso
    st.success(texto)
    if temporal:
        st.caption("Contraseña temporal. Comuníquela en persona; no se volverá a mostrar. "
                   "El usuario deberá cambiarla al iniciar sesión.")
        st.code(temporal, language=None)

lista = usuarios.listar()
solicitudes = usuarios.solicitudes_pendientes(administrador)
pestana_lista, pestana_nuevo, pestana_solicitudes = st.tabs(
    ["Usuarios", "Nuevo usuario", f"Solicitudes de acceso ({len(solicitudes)})"])

with pestana_lista:
    tabla = pd.DataFrame([{
        "Nombre": fila["nombre"],
        "Usuario": fila["usuario"],
        "Cargo": permisos.NOMBRES_CARGO[fila["cargo"]],
        "Área": fila["area"],
        "Correo": fila["correo"],
        "Teléfono": fila["tel_mx"],
        "Estado": "Bloqueado" if fila["bloqueado"] else ("Activo" if fila["activo"] else "Inactivo"),
    } for fila in lista])
    st.dataframe(tabla, hide_index=True, width="stretch")

    por_id = {fila["id_usuario"]: fila for fila in lista}
    id_elegido = st.selectbox(
        "Usuario a modificar", list(por_id), index=None, placeholder="Seleccione un usuario",
        format_func=lambda id_usuario: f"{por_id[id_usuario]['nombre']} ({por_id[id_usuario]['usuario']})")

    if id_elegido is not None:
        elegido = por_id[id_elegido]
        st.subheader("Editar datos")
        datos = formulario(f"editar_{id_elegido}", elegido)
        if datos and guardar(lambda: usuarios.editar(administrador, id_elegido, datos)):
            if id_elegido == administrador["id_usuario"]:
                administrador.update(nombre=datos["nombre"].strip(), area=datos["area"])
            avisar("Datos actualizados.")

        st.subheader("Acciones")
        restablecer, estado = st.columns(2)
        with restablecer:
            if st.button("Restablecer contraseña", width="stretch"):
                temporal = usuarios.restablecer_contrasena(administrador, id_elegido)
                avisar(f"Se restableció la contraseña de {elegido['usuario']}.", temporal)
        with estado:
            activo = bool(elegido["activo"])
            if st.button("Desactivar" if activo else "Reactivar", width="stretch"):
                if guardar(lambda: usuarios.cambiar_estado(administrador, id_elegido, not activo)):
                    avisar(f"Se {'desactivó' if activo else 'reactivó'} a {elegido['usuario']}.")

with pestana_nuevo:
    datos = formulario("nuevo_usuario")
    if datos:
        resultado = {}

        def crear():
            problemas, resultado["temporal"] = usuarios.crear(administrador, datos)
            return problemas

        if guardar(crear):
            avisar(f"Se creó el usuario {datos['usuario'].strip()}.", resultado["temporal"])

with pestana_solicitudes:
    if not solicitudes:
        st.info("No hay solicitudes pendientes.")
    for solicitud in solicitudes:
        with st.container(border=True):
            st.caption(solicitud["fecha_creacion"].strftime("%d/%m/%Y %H:%M"))
            st.write(solicitud["contenido"])
            st.caption("Restablezca la contraseña desde la pestaña Usuarios y después marque la "
                       "solicitud como revisada.")
            with st.form(f"solicitud_{solicitud['id_noti']}"):
                respuesta = st.text_input("Comentario (opcional)")
                if st.form_submit_button("Marcar como revisado"):
                    usuarios.marcar_solicitud_revisada(administrador, solicitud["id_noti"], respuesta)
                    avisar("Solicitud marcada como revisada.")
