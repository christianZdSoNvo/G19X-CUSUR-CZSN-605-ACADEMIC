from urllib.parse import quote

import pandas as pd
import streamlit as st

from backend import analitica, errores, graficas, manuales, parametros, permisos
from backend.interfaz import AVATAR, NOMBRE

# Vistas compartidas entre páginas: historial (su página y el drill-down de paneles),
# manuales y contacto de soporte (Soporte, Manuales y Configuración)

ASUNTO_SOPORTE = f"Soporte – {NOMBRE}"


def fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


def foto_perfil(foto, ancho=110):
    # Foto de perfil de un talento o usuario; sin foto, el avatar genérico
    st.image(bytes(foto) if foto else AVATAR, width=ancho)


def encabezado_talento(talento, detalle):
    # Foto, nombre y una línea de datos del talento (Talentos, Historial y Reportes)
    foto, datos = st.columns([1, 5], vertical_alignment="center")
    with foto:
        foto_perfil(talento.get("foto"))
    datos.subheader(talento["nombre"])
    datos.caption(detalle)


def editor_foto(clave, actual, cambiar):
    # Cargar o quitar una foto de perfil. cambiar(bytes o None) la guarda; devuelve el
    # texto del aviso si hubo cambio. E-402 se muestra aquí mismo.
    version = st.session_state.get(f"{clave}_version", 0)
    archivo = st.file_uploader("Foto de perfil (PNG o JPG, máximo 5 MB)", type=["png", "jpg", "jpeg"],
                               max_upload_size=manuales.MAX_IMAGEN_MB, key=f"{clave}_archivo_{version}")
    guardar, quitar = st.columns(2)
    try:
        if guardar.button("Guardar foto", type="primary", disabled=archivo is None, width="stretch",
                          key=f"{clave}_guardar"):
            cambiar(archivo.getvalue())
            aviso = "Se actualizó la foto de perfil."
        elif actual and quitar.button("Quitar foto", width="stretch", key=f"{clave}_quitar"):
            cambiar(None)
            aviso = "Se quitó la foto de perfil."
        else:
            return None
    except errores.ErrorSistema as error:
        if error.codigo != "E-402":
            raise
        st.error(error.mensaje)
        st.caption("Código de error: E-402")
        return None
    # Una clave nueva vacía el selector de archivo
    st.session_state[f"{clave}_version"] = version + 1
    return aviso


def historial_talento(usuario, talento, clave):
    # Línea de tiempo del talento con sus evaluaciones y eventos (PRD, 13.3)
    datos = analitica.historial(usuario, talento["id_talento"])
    if datos is None:
        return
    if not datos["evaluaciones"]:
        st.info("Este talento aún no tiene evaluaciones con IA; la línea de tiempo muestra solo sus eventos.")
    st.plotly_chart(graficas.linea_de_tiempo(talento["fecha_ingreso"], datos["evaluaciones"], datos["eventos"]),
                    key=f"linea_{clave}")

    if datos["evaluaciones"]:
        st.markdown("**Evaluaciones**")
        st.dataframe(pd.DataFrame([{
            "Fecha": fecha(fila["fecha_evaluacion"]),
            "Puntuación": fila["puntuacion_talento_por_ia"],
            "Potencial": fila["potencial_crecimiento_nivel"].capitalize(),
            "Clasificación 9-box": fila["clasificacion_9box"],
        } for fila in reversed(datos["evaluaciones"])]), hide_index=True, width="stretch")
    if datos["eventos"]:
        st.markdown("**Eventos**")
        st.dataframe(pd.DataFrame([{
            "Fecha": fecha(evento["fecha_evento"]),
            "Tipo": analitica.TIPOS_EVENTO[evento["tipo_evento"]],
            "Descripción": evento["descripcion"],
        } for evento in reversed(datos["eventos"])]), hide_index=True, width="stretch")


def enlace_correo(correo, codigo=""):
    # mailto: con el asunto del PRD (12.3) y, si existe, el último código de error
    cuerpo = f"Código de error: {codigo}\n\n" if codigo else ""
    cuerpo += "Describa qué estaba haciendo y qué ocurrió:\n"
    return f"mailto:{correo}?subject={quote(ASUNTO_SOPORTE)}&body={quote(cuerpo)}"


def contacto_talento(talento):
    # Datos para ponerse en contacto con el talento (Reportes); el correo abre el cliente
    # de correo del equipo, porque el sistema no envía correos
    with st.container(border=True):
        st.markdown("**Contacto del talento**")
        correo, telefono = st.columns(2)
        correo.caption("Correo")
        correo.code(talento["correo"], language=None)
        telefono.caption("Teléfono")
        telefono.code(talento["tel_mx"], language=None)
        st.link_button("Escribir correo al talento", f"mailto:{talento['correo']}", icon=":material/mail:")


def contacto_soporte(clave):
    # Tarjeta de contacto (PRD, 13.6): nombre, correo y teléfono de Configuracion_sistema,
    # código de error opcional y botón "Escribir correo"
    contacto = parametros.contacto_soporte()
    with st.container(border=True):
        st.markdown(f"**{contacto['nombre']}**")
        st.write(f"Correo: {contacto['correo']}")
        st.write(f"Teléfono: {contacto['telefono']}")
        codigo = st.text_input("Código de error (opcional)", st.session_state.get("ultimo_codigo_error", ""),
                               max_chars=5, key=f"codigo_{clave}",
                               help="Se llena con el último código de error que mostró el sistema.")
        if parametros.definido(contacto["correo"]):
            st.link_button("Escribir correo", enlace_correo(contacto["correo"], codigo.strip().upper()),
                           type="primary", icon=":material/mail:")
        else:
            st.button("Escribir correo", disabled=True, key=f"correo_{clave}",
                      help="El Administrador de RH aún no define el correo de soporte.")


def consulta_manuales(usuario, clave, elegir_cargo=False):
    # Lista filtrable por sección y texto (PRD, 13.6); E-401 si no hay manuales.
    # Por omisión, los manuales del cargo del usuario; con elegir_cargo (Administrador,
    # página Manuales) puede consultar también los del Encargado.
    cargo = usuario["cargo"]
    if elegir_cargo:
        cargo = st.radio("Manuales de", manuales.CARGOS, format_func=permisos.NOMBRES_CARGO.get,
                         horizontal=True, key=f"cargo_{clave}")
    if not manuales.hay_manuales(usuario, cargo):
        if cargo != usuario["cargo"]:
            st.info(f"No hay manuales para el {permisos.NOMBRES_CARGO[cargo]}.")
            return
        correo = parametros.contacto_soporte()["correo"]
        st.warning(errores.CATALOGO["E-401"].format(correo_soporte=correo))
        st.caption("Código de error: E-401")
        contacto_soporte(f"{clave}_sin_manuales")
        return
    izquierda, derecha = st.columns(2)
    seccion = izquierda.selectbox("Sección del sistema", manuales.secciones_de(cargo), index=None,
                                  placeholder="Todas las secciones", key=f"seccion_{clave}_{cargo}")
    texto = derecha.text_input("Buscar en los manuales", key=f"buscar_{clave}")
    encontrados = manuales.listar(usuario, seccion, texto, cargo)
    if not encontrados:
        st.info("No hay manuales que coincidan con la búsqueda.")
    for manual in encontrados:
        with st.expander(manual["seccion_software"], expanded=len(encontrados) == 1):
            mostrar_manual(manual)


def mostrar_manual(manual):
    if manual["contenido_texto"]:
        st.write(manual["contenido_texto"])
    for imagen in manual["imagenes"]:
        st.image(bytes(imagen["imagen"]))
    if manual["contenido_enlace"]:
        st.markdown(f"[{manual['contenido_enlace']}]({manual['contenido_enlace']})")
    st.caption(f"Actualizado el {manual['fecha_actualizacion']:%d/%m/%Y} por {manual['edito']}.")
