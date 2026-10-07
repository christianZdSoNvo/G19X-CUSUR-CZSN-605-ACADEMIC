import datetime

import pandas as pd
import streamlit as st

from backend import alertas, catalogos, errores, notificaciones, permisos, sesion, talentos, vistas

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "notificaciones")
es_administrador = permisos.es_administrador(usuario)

NOMBRE_GRADO = {"bajo": "Bajo", "medio": "Medio", "alto": "Alto"}
# Colores del sistema por grado: rojo (alto), dorado (medio) y azul oscuro (bajo)
COLOR_GRADO = {"alto": ("#B22234", "#FFFFFF"), "medio": ("#C9A227", "#0B1F3A"), "bajo": ("#0B1F3A", "#FFFFFF")}
MARKDOWN_GRADO = {"alto": "red", "medio": "orange", "bajo": "blue"}
VALORES_INICIALES = {"noti_tipo": notificaciones.TIPOS_MANUALES[0], "noti_destinatario": None,
                     "noti_talento": None, "noti_grado": "bajo", "noti_texto": ""}


def avisar(texto):
    st.session_state["aviso_notificaciones"] = texto
    st.rerun()


def fecha_hora(valor):
    return valor.strftime("%d/%m/%Y %H:%M") if valor else ""


def errores_de(problemas):
    for mensaje in problemas.values():
        st.error(mensaje)


# --- Bandeja (PRD, 13.7) ---

def bandeja():
    vista = st.segmented_control("Mostrar", ["Recibidas", "Enviadas"], default="Recibidas", required=True,
                                 key="bandeja_vista")
    estado_col, grado_col = st.columns(2)
    estado = estado_col.selectbox("Estado", notificaciones.ESTADOS, index=None, placeholder="Todos",
                                  format_func=str.capitalize, key="bandeja_estado")
    grados = grado_col.multiselect("Grado de emergencia", notificaciones.GRADOS, format_func=NOMBRE_GRADO.get,
                                   placeholder="Todos", key="bandeja_grados")
    consulta = notificaciones.recibidas if vista == "Recibidas" else notificaciones.enviadas
    lista = consulta(usuario, estado, grados)
    if not lista:
        st.info("No hay notificaciones " + ("recibidas." if vista == "Recibidas" else "enviadas."))
        return

    tabla = pd.DataFrame([{
        "Fecha": fecha_hora(n["fecha_creacion"]),
        "Grado": NOMBRE_GRADO[n["grado_emergencia"]],
        "Tipo": notificaciones.TIPOS[n["tipo"]],
        "Destinatario": n["destinatario"],
        "Emisor": notificaciones.nombre_emisor(n),
        "Talento": n["talento"] or "",
        "Estado": n["estado"].capitalize(),
    } for n in lista])

    def color(valor):
        fondo, letra = COLOR_GRADO[valor.lower()]
        return f"background-color: {fondo}; color: {letra}; font-weight: bold"

    seleccion = st.dataframe(tabla.style.map(color, subset=["Grado"]), hide_index=True, width="stretch",
                             on_select="rerun", selection_mode="single-row", key=f"bandeja_tabla_{vista}")
    pendientes = sum(n["estado"] == "pendiente" for n in lista)
    st.caption(f"{len(lista)} notificación(es), {pendientes} pendiente(s). Seleccione un renglón para abrirla.")
    if seleccion.selection.rows:
        detalle(lista[seleccion.selection.rows[0]], recibida=vista == "Recibidas")


def detalle(notificacion, recibida):
    with st.container(border=True):
        # Criterio de la notificación (PRD, 6.6)
        grado = notificacion["grado_emergencia"]
        st.markdown(f"**{notificacion['destinatario']}** [IMPORTANCIA: "
                    f":{MARKDOWN_GRADO[grado]}[**{grado.upper()}**]]")
        st.markdown(notificacion["contenido"].replace("\n", "  \n"))
        st.markdown(f"**Emisor:** {notificaciones.nombre_emisor(notificacion)}")
        st.caption(f"{notificaciones.TIPOS[notificacion['tipo']]} · {fecha_hora(notificacion['fecha_creacion'])} · "
                   f"Estado: {notificacion['estado']}")

        if notificacion["id_talento"]:
            st.markdown(f"**Talento relacionado:** {notificacion['talento']} (ID {notificacion['id_talento']}, "
                        f"{notificacion['area_talento']})")
            talento_col, historial_col = st.columns(2)
            if talento_col.button("Abrir en Talentos", key=f"noti_talento_{notificacion['id_noti']}",
                                  width="stretch"):
                st.session_state["talentos_talento"] = notificacion["id_talento"]
                st.switch_page("paginas/talentos.py")
            if historial_col.button("Abrir en Historial", key=f"noti_historial_{notificacion['id_noti']}",
                                    width="stretch"):
                st.session_state["historial_talento"] = notificacion["id_talento"]
                st.switch_page("paginas/historial.py")
        if notificacion["tipo"] == "restablecer_acceso" and es_administrador:
            if st.button("Ir a Gestión de usuarios", key=f"noti_usuarios_{notificacion['id_noti']}"):
                st.switch_page("paginas/gestion_usuarios.py")

        if notificacion["estado"] == "revisado":
            st.success(f"Revisada el {fecha_hora(notificacion['fecha_revision'])}."
                       + (f" Respuesta: {notificacion['respuesta']}" if notificacion["respuesta"] else ""))
        elif recibida:
            respuesta = ""
            if notificacion["id_emisor"] or es_administrador:
                respuesta = st.text_area("Respuesta (opcional)", max_chars=notificaciones.MAX_RESPUESTA,
                                         key=f"noti_respuesta_{notificacion['id_noti']}")
            if st.button("Marcar como revisado", type="primary", key=f"noti_revisar_{notificacion['id_noti']}"):
                problema = notificaciones.marcar_revisada(usuario, notificacion["id_noti"], respuesta)
                if problema:
                    st.error(problema)
                else:
                    avisar("La notificación se marcó como revisada.")
        else:
            st.info("Pendiente de revisión por el destinatario.")


# --- Nueva notificación (PRD, 6.6 y 13.7) ---

def nueva():
    lista_destinatarios = notificaciones.destinatarios(usuario)
    if not lista_destinatarios:
        st.info("No hay destinatarios disponibles.")
        return
    por_id = {d["id_usuario"]: d for d in lista_destinatarios}
    if st.session_state.pop("noti_limpiar", False):
        # Tras enviar, el formulario queda en blanco: borrar las claves no basta, porque el
        # navegador vuelve a mandar lo que tenía escrito; hay que asignar los valores iniciales
        st.session_state.update(VALORES_INICIALES)
    # Tipo y grado toman su valor inicial aquí (no con index/default) para poder reiniciarlos
    st.session_state.setdefault("noti_tipo", VALORES_INICIALES["noti_tipo"])
    st.session_state.setdefault("noti_grado", VALORES_INICIALES["noti_grado"])

    tipo = st.selectbox("Tipo", notificaciones.TIPOS_MANUALES, format_func=notificaciones.TIPOS.get, index=None,
                        key="noti_tipo")
    if not es_administrador and len(por_id) == 1:
        # El Encargado escribe al Administrador (PRD, 6.7)
        id_destinatario = next(iter(por_id))
        st.text_input("Destinatario", por_id[id_destinatario]["nombre"], disabled=True)
    else:
        id_destinatario = st.selectbox(
            "Destinatario", list(por_id), index=None, placeholder="Seleccione un destinatario", key="noti_destinatario",
            format_func=lambda i: f"{por_id[i]['nombre']} ({permisos.NOMBRES_CARGO[por_id[i]['cargo']]} · "
                                  f"{por_id[i]['area']})")

    # Un Encargado solo puede recibir notificaciones de talentos de su área
    destinatario = por_id.get(id_destinatario)
    area = destinatario["area"] if destinatario and destinatario["cargo"] == permisos.ENCARGADO else None
    opciones = {fila["id_talento"]: fila for fila in talentos.buscar(usuario, area=area)}
    if st.session_state.get("noti_talento") not in opciones:
        st.session_state.pop("noti_talento", None)
    id_talento = st.selectbox(
        "Talento" + ("" if tipo in notificaciones.CON_TALENTO else " (opcional)"), list(opciones), index=None,
        placeholder="Ninguno", key="noti_talento",
        format_func=lambda i: f"{i} - {opciones[i]['nombre']} ({opciones[i]['area']})")
    grado = st.segmented_control("Grado de emergencia", notificaciones.GRADOS, format_func=NOMBRE_GRADO.get,
                                 required=True, key="noti_grado")
    ultimo_codigo = st.session_state.get("ultimo_codigo_error")
    if tipo == "error_sistema" and ultimo_codigo:
        st.caption(f"Último código de error de esta sesión: **{ultimo_codigo}** (inclúyalo en el texto).")
    ayuda = {"correccion_datos": "Indique el campo y el valor correcto.",
             "reevaluacion": "Explique por qué debe reevaluarse al talento.",
             "error_sistema": "Describa qué estaba haciendo y el código de error."}.get(tipo)
    contenido = st.text_area("Texto", max_chars=notificaciones.MAX_TEXTO, placeholder=ayuda, key="noti_texto")

    datos = {"tipo": tipo, "id_destinatario": id_destinatario, "id_talento": id_talento,
             "grado_emergencia": grado, "contenido": contenido}
    nombre_destinatario = destinatario["nombre"] if destinatario else "(sin destinatario)"
    st.markdown("**Vista previa**")
    with st.container(border=True):
        st.markdown(f"**{nombre_destinatario}** [IMPORTANCIA: :{MARKDOWN_GRADO[grado]}[**{grado.upper()}**]]")
        st.markdown(contenido.strip().replace("\n", "  \n") or "_(texto de la notificación)_")
        st.markdown(f"**Emisor:** {usuario['nombre']}")

    if st.button("Enviar", type="primary"):
        try:
            problemas, _ = notificaciones.enviar(usuario, datos)
        except errores.ErrorSistema as error:
            if error.codigo != "E-001":
                raise
            sin_conexion(notificaciones.borrador(usuario, datos, nombre_destinatario))
            return
        if problemas:
            errores_de(problemas)
            return
        st.session_state["noti_limpiar"] = True
        avisar(f"Se envió la notificación a {nombre_destinatario}.")


def sin_conexion(borrador):
    # Flujo alterno (PRD, 6.6): sin BD se sugiere guardar el texto fuera del sistema
    st.error(errores.CATALOGO["E-001"] + " (código E-001)")
    st.markdown("**Sugerencia:** copie o guarde el texto de la notificación en un medio externo (archivo, bloc "
                "de notas o bitácora) para registrarla cuando se restablezca la conexión.")
    st.code(f"[Borrador para respaldar]\n{borrador}", language=None, wrap_lines=True)
    st.download_button("Guardar en archivo", borrador.encode("utf-8-sig"), mime="text/plain", on_click="ignore",
                       file_name=f"Notificacion_pendiente_{datetime.datetime.now():%Y%m%d_%H%M}.txt")


# --- Alertas (PRD, 6.6, 9.8 y 13.7) ---

def reglas():
    lista = alertas.listar(usuario)
    if not es_administrador:
        st.caption("Sus alertas son solo de su área y usted es el destinatario.")
    if not lista:
        st.info("No hay alertas configuradas.")
        if es_administrador and st.button("Crear las alertas sugeridas",
                                          help="Las del PRD: puntuación ±10, cambio de nivel, desempeño -10 y "
                                               f"{alertas.DIAS_POR_OMISION} días sin evaluar; para usted y todas "
                                               "las áreas."):
            for regla in alertas.sugeridas(usuario):
                alertas.crear(usuario, regla)
            avisar("Se crearon las alertas sugeridas.")
    else:
        tabla = pd.DataFrame([{
            "Nombre": regla["nombre"],
            "Regla": alertas.descripcion(regla),
            "Área": regla["area"] or "Todas",
            "Destinatario": regla["destinatario"] + ("" if regla["destinatario_activo"] else " (inactivo)"),
            "Grado": NOMBRE_GRADO[regla["grado_emergencia"]],
            "Activa": bool(regla["activa"]),
        } for regla in lista])
        editada = st.data_editor(tabla, hide_index=True, width="stretch", key="alertas_tabla",
                                 disabled=[c for c in tabla.columns if c != "Activa"])
        for regla, activa in zip(lista, editada["Activa"]):
            if activa != bool(regla["activa"]):
                if not alertas.puede_modificar(usuario, regla):
                    st.warning(f"La alerta \"{regla['nombre']}\" la configuró el Administrador; no puede cambiarla.")
                    continue
                alertas.cambiar_activa(usuario, regla["id_alerta"], bool(activa))
                st.session_state.pop("alertas_tabla", None)
                avisar(f"La alerta \"{regla['nombre']}\" quedó {'activa' if activa else 'inactiva'}.")

    st.divider()
    modificables = {regla["id_alerta"]: regla for regla in lista if alertas.puede_modificar(usuario, regla)}
    elegida = st.selectbox("Crear o editar", [None, *modificables], key="alertas_elegida",
                           format_func=lambda i: "Nueva alerta" if i is None else f"Editar: {modificables[i]['nombre']}")
    formulario_regla(modificables.get(elegida))


def formulario_regla(regla):
    clave = f"alerta_{regla['id_alerta'] if regla else 'nueva'}"
    if f"{clave}_nombre" not in st.session_state:
        inicial = regla or {"nombre": "", "indicador": "puntuacion_ia", "condicion": "disminuye", "umbral": None,
                            "area": None, "id_destinatario": usuario["id_usuario"], "grado_emergencia": "medio",
                            "activa": True}
        for campo, valor in inicial.items():
            st.session_state[f"{clave}_{campo}"] = valor

    nombre = st.text_input("Nombre", max_chars=alertas.MAX_NOMBRE, key=f"{clave}_nombre")
    indicador_col, condicion_col, umbral_col = st.columns(3)
    indicador = indicador_col.selectbox("Indicador", list(alertas.INDICADORES), format_func=alertas.INDICADORES.get,
                                        key=f"{clave}_indicador")
    condiciones = alertas.CONDICIONES_POR_INDICADOR[indicador]
    if st.session_state.get(f"{clave}_condicion") not in condiciones:
        st.session_state[f"{clave}_condicion"] = condiciones[0]
    condicion = condicion_col.selectbox("Condición", condiciones, format_func=alertas.CONDICIONES.get,
                                        key=f"{clave}_condicion", disabled=len(condiciones) == 1)
    umbral = None
    if alertas.usa_umbral(indicador):
        minimo, maximo = alertas.LIMITES_UMBRAL[indicador]
        if not isinstance(st.session_state.get(f"{clave}_umbral"), int) or \
                not minimo <= st.session_state[f"{clave}_umbral"] <= maximo:
            st.session_state[f"{clave}_umbral"] = alertas.umbral_por_omision(indicador)
        umbral = umbral_col.number_input("Días" if indicador == "sin_evaluacion" else "Puntos", minimo, maximo,
                                         step=1, key=f"{clave}_umbral")
    else:
        umbral_col.text_input("Umbral", "No aplica", disabled=True, key=f"{clave}_sin_umbral")

    area_col, destinatario_col = st.columns(2)
    if es_administrador:
        area = area_col.selectbox("Área", catalogos.AREAS, index=None, placeholder="Todas las áreas",
                                  key=f"{clave}_area")
        por_id = {d["id_usuario"]: d for d in alertas.destinatarios(usuario)}
        if st.session_state.get(f"{clave}_id_destinatario") not in por_id:
            st.session_state[f"{clave}_id_destinatario"] = usuario["id_usuario"]
        id_destinatario = destinatario_col.selectbox(
            "Destinatario", list(por_id), key=f"{clave}_id_destinatario",
            format_func=lambda i: f"{por_id[i]['nombre']} ({permisos.NOMBRES_CARGO[por_id[i]['cargo']]} · "
                                  f"{por_id[i]['area']})")
    else:
        area, id_destinatario = usuario["area"], usuario["id_usuario"]
        area_col.text_input("Área", area, disabled=True, key=f"{clave}_area_fija")
        destinatario_col.text_input("Destinatario", usuario["nombre"], disabled=True, key=f"{clave}_dest_fijo")
    grado_col, activa_col = st.columns(2)
    with grado_col:
        grado = st.segmented_control("Grado de emergencia", alertas.GRADOS, format_func=NOMBRE_GRADO.get,
                                     required=True, key=f"{clave}_grado_emergencia")
    with activa_col:
        activa = st.toggle("Activa", key=f"{clave}_activa")

    datos = {"nombre": nombre, "indicador": indicador, "condicion": condicion,
             "umbral": int(umbral) if umbral is not None else None, "area": area,
             "id_destinatario": id_destinatario, "grado_emergencia": grado, "activa": activa}
    guardar_col, eliminar_col = st.columns(2)
    if guardar_col.button("Guardar", type="primary", key=f"{clave}_guardar", width="stretch"):
        if regla:
            problemas = alertas.editar(usuario, regla["id_alerta"], datos)
        else:
            problemas, _ = alertas.crear(usuario, datos)
        if problemas:
            errores_de(problemas)
        else:
            olvidar(clave)
            avisar(f"Se guardó la alerta \"{nombre.strip()}\".")
    if regla:
        confirmar = eliminar_col.checkbox("Confirmar eliminación", key=f"{clave}_confirmar")
        if eliminar_col.button("Eliminar", key=f"{clave}_eliminar", disabled=not confirmar, width="stretch"):
            alertas.eliminar(usuario, regla["id_alerta"])
            olvidar(clave)
            st.session_state.pop("alertas_elegida", None)
            avisar(f"Se eliminó la alerta \"{regla['nombre']}\".")


def olvidar(clave):
    for llave in [llave for llave in st.session_state if str(llave).startswith(f"{clave}_")]:
        st.session_state.pop(llave, None)
    st.session_state.pop("alertas_tabla", None)


# --- Página ---

st.title("Notificaciones y alertas")
aviso = st.session_state.pop("aviso_notificaciones", None)
if aviso:
    st.success(aviso)

# Una solicitud iniciada desde Talentos llega con el tipo y el talento elegidos
solicitud = st.session_state.pop("nueva_notificacion", None)
if solicitud:
    st.session_state["noti_tipo"] = solicitud["tipo"]
    st.session_state["noti_talento"] = solicitud["id_talento"]
pestanas = ["Bandeja", "Nueva notificación", "Alertas"]
pestana_bandeja, pestana_nueva, pestana_alertas = st.tabs(
    pestanas, default="Nueva notificación" if solicitud else None)
with pestana_bandeja:
    bandeja()
with pestana_nueva:
    nueva()
with pestana_alertas:
    reglas()
