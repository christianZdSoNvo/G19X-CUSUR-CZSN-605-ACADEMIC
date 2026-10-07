import datetime

import pandas as pd
import streamlit as st

from backend import catalogos, errores, evaluaciones, ia, permisos, sesion, talentos, vistas

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "ver_talentos")
puede_editar = permisos.puede(usuario, "editar_talentos")
puede_evaluar = permisos.puede(usuario, "evaluar_ia")
if puede_evaluar:
    # Mantiene el modelo en memoria mientras el Administrador trabaja con talentos
    ia.precargar()

ETIQUETAS = {
    "nombre": "Nombre completo",
    "area": "Área",
    "correo": "Correo",
    "tel_mx": "Teléfono (10 dígitos)",
    "fecha_ingreso": "Fecha de ingreso",
    "desempeno_previo": "Desempeño previo (0-100)",
    "competencias": "Competencias",
    "capacitacion": "Resultados de capacitación",
    "experiencia": "Experiencia",
    "objetivos_futuros": "Objetivos futuros",
    "liderazgo_previo": "Liderazgo previo",
}
FECHA_MINIMA = datetime.date(1950, 1, 1)
CRITERIOS_IA = {
    "desempeno_pre_ev": "Desempeño previo",
    "resultados_cap_ev": "Resultados de capacitación",
    "experiencia_lab_ev": "Experiencia laboral",
    "objetivos_fut_ev": "Objetivos futuros",
    "competencias_ev": "Competencias",
    "liderazgo_prev_ev": "Liderazgo previo",
}


def fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


def avisar(texto):
    # El aviso se muestra después de recargar, para que la lista ya incluya el cambio
    st.session_state["aviso_talentos"] = texto
    st.rerun()


def olvidar(clave):
    # Borra los valores capturados para que el formulario se vuelva a llenar
    for campo in talentos.CAMPOS:
        st.session_state.pop(f"{clave}_{campo}", None)


def formulario(clave, talento=None):
    # Formulario de alta y edición (PRD, 13.8). Devuelve (botón pulsado, datos, espacios
    # para los errores): los errores se escriben debajo de cada campo después de guardar.
    for campo in talentos.CAMPOS:
        if f"{clave}_{campo}" not in st.session_state:
            valor = talento[campo] if talento else None
            if campo in talentos.INDICADORES and valor == talentos.SIN_REGISTRO:
                valor = ""
            if valor is None and campo not in ("area", "fecha_ingreso", "desempeno_previo"):
                valor = ""
            st.session_state[f"{clave}_{campo}"] = valor

    espacios = {}
    with st.form(clave):
        izquierda, derecha = st.columns(2)
        with izquierda:
            st.markdown("**Datos generales**")
            st.text_input(ETIQUETAS["nombre"], key=f"{clave}_nombre", max_chars=50)
            espacios["nombre"] = st.empty()
            st.selectbox(ETIQUETAS["area"], catalogos.AREAS, key=f"{clave}_area",
                         placeholder="Seleccione un área")
            espacios["area"] = st.empty()
            st.text_input(ETIQUETAS["correo"], key=f"{clave}_correo", max_chars=70)
            espacios["correo"] = st.empty()
            st.text_input(ETIQUETAS["tel_mx"], key=f"{clave}_tel_mx", max_chars=10)
            espacios["tel_mx"] = st.empty()
            st.date_input(ETIQUETAS["fecha_ingreso"], key=f"{clave}_fecha_ingreso", format="DD/MM/YYYY",
                          min_value=FECHA_MINIMA, max_value=datetime.date.today())
            espacios["fecha_ingreso"] = st.empty()
        with derecha:
            st.markdown("**Indicadores**")
            st.number_input(ETIQUETAS["desempeno_previo"], key=f"{clave}_desempeno_previo",
                            min_value=0, max_value=100, step=1, placeholder="Sin registro")
            espacios["desempeno_previo"] = st.empty()
            for campo, maximo in talentos.INDICADORES.items():
                st.text_area(ETIQUETAS[campo], key=f"{clave}_{campo}", max_chars=maximo, height=100,
                             placeholder=talentos.SIN_REGISTRO)
                espacios[campo] = st.empty()

        botones = st.columns(3 if talento else 2)
        pulsado = None
        if botones[0].form_submit_button("Guardar", type="primary", width="stretch"):
            pulsado = "guardar"
        if botones[1].form_submit_button("Cancelar", width="stretch"):
            pulsado = "cancelar"
        if talento and botones[2].form_submit_button("Dar de baja", width="stretch"):
            pulsado = "baja"

    datos = {campo: st.session_state[f"{clave}_{campo}"] for campo in talentos.CAMPOS}
    return pulsado, datos, espacios


def guardar(accion, espacios):
    # Cada error se muestra debajo de su campo, con el código E-004 (correo repetido)
    # o E-003 (dato inválido) arriba de la pantalla; los demás códigos pasan a la
    # pantalla de error general
    try:
        problemas = accion()
    except errores.ErrorSistema as error:
        if error.codigo == "E-004":
            # Otro registro tomó el correo entre la revisión y el guardado
            problemas = {"correo": talentos.DUPLICADO}
        elif error.codigo == "E-003":
            st.error(f"{error.mensaje} (E-003)")
            return False
        else:
            raise
    for campo, mensaje in problemas.items():
        espacios[campo].error(mensaje)
    if problemas:
        codigo = "E-004" if problemas.get("correo") == talentos.DUPLICADO else "E-003"
        st.error(f"{errores.CATALOGO[codigo]} ({codigo})")
    return not problemas


def ficha(talento):
    # Perfil de solo consulta (Encargado de área)
    izquierda, derecha = st.columns(2)
    with izquierda:
        st.markdown("**Datos generales**")
        for campo in talentos.GENERALES:
            valor = fecha(talento[campo]) if campo == "fecha_ingreso" else talento[campo]
            st.markdown(f"**{ETIQUETAS[campo]}:** {valor}")
    with derecha:
        st.markdown("**Indicadores**")
        desempeno = talento["desempeno_previo"]
        st.markdown(f"**{ETIQUETAS['desempeno_previo']}:** "
                    f"{talentos.SIN_REGISTRO if desempeno is None else desempeno}")
        for campo in talentos.INDICADORES:
            st.markdown(f"**{ETIQUETAS[campo]}:** {talento[campo]}")
    st.caption(f"Última modificación: {fecha(talento['fecha_modificacion'])}")

    # El Encargado pide los cambios al Administrador por notificación (PRD, 6.6)
    correccion, reevaluacion = st.columns(2)
    for columna, tipo, etiqueta in ((correccion, "correccion_datos", "Solicitar corrección de datos"),
                                    (reevaluacion, "reevaluacion", "Solicitar reevaluación con IA")):
        if columna.button(etiqueta, key=f"solicitar_{tipo}", width="stretch"):
            st.session_state["nueva_notificacion"] = {"tipo": tipo, "id_talento": talento["id_talento"]}
            st.switch_page("paginas/notificaciones.py")


def edicion(talento):
    clave = f"editar_{talento['id_talento']}"
    clave_baja = f"baja_{talento['id_talento']}"
    pulsado, datos, espacios = formulario(clave, talento)
    if pulsado == "guardar":
        if guardar(lambda: talentos.editar(usuario, talento["id_talento"], datos), espacios):
            olvidar(clave)
            avisar(f"Se actualizaron los datos de {datos['nombre'].strip()}.")
    elif pulsado == "cancelar":
        olvidar(clave)
        st.session_state.pop(clave_baja, None)
        st.rerun()
    elif pulsado == "baja":
        st.session_state[clave_baja] = True

    if st.session_state.get(clave_baja):
        with st.container(border=True):
            st.markdown(f"**Dar de baja a {talento['nombre']}**")
            st.caption("El talento dejará de aparecer en listas, búsquedas y paneles; sus evaluaciones "
                       "y eventos se conservan. Podrá reactivarse desde \"Talentos dados de baja\".")
            motivo = st.text_area("Motivo de la baja", max_chars=talentos.MAX_MOTIVO, key=f"{clave_baja}_motivo")
            espacio_motivo = st.empty()
            confirmado = st.checkbox("Confirmo que deseo dar de baja a este talento", key=f"{clave_baja}_ok")
            confirmar, cancelar = st.columns(2)
            if confirmar.button("Confirmar baja", type="primary", width="stretch", disabled=not confirmado):
                problemas = talentos.dar_de_baja(usuario, talento["id_talento"], motivo)
                if problemas:
                    espacio_motivo.error(problemas["motivo"])
                else:
                    st.session_state.pop(clave_baja, None)
                    olvidar(clave)
                    avisar(f"Se dio de baja a {talento['nombre']}.")
            if cancelar.button("Cancelar baja", width="stretch"):
                st.session_state.pop(clave_baja, None)
                st.rerun()


def alta():
    clave = "nuevo_talento"
    pulsado, datos, espacios = formulario(clave)
    if pulsado == "guardar":
        resultado = {}

        def crear():
            problemas, resultado["id"] = talentos.crear(usuario, datos)
            return problemas

        try:
            if guardar(crear, espacios):
                olvidar(clave)
                avisar(f"Se registró a {datos['nombre'].strip()} con el ID {resultado['id']}.")
        except talentos.TalentoDeBaja as de_baja:
            st.session_state["ofrecer_reactivar"] = (de_baja.id_talento, de_baja.nombre)
    elif pulsado == "cancelar":
        olvidar(clave)
        st.session_state.pop("ofrecer_reactivar", None)
        st.rerun()

    # El correo es de un talento dado de baja: se ofrece reactivarlo (PRD, 9.1)
    oferta = st.session_state.get("ofrecer_reactivar")
    if oferta:
        id_talento, nombre = oferta
        st.warning(f"El correo pertenece a {nombre} (ID {id_talento}), que está dado de baja. "
                   "Puede reactivarlo en lugar de crear un registro nuevo y después actualizar sus datos "
                   "desde la lista.")
        reactivar, descartar = st.columns(2)
        if reactivar.button(f"Reactivar a {nombre}", type="primary", width="stretch"):
            talentos.reactivar(usuario, id_talento)
            st.session_state.pop("ofrecer_reactivar")
            olvidar(clave)
            avisar(f"Se reactivó a {nombre} (ID {id_talento}).")
        if descartar.button("No reactivar", width="stretch"):
            st.session_state.pop("ofrecer_reactivar")
            st.rerun()


def lista():
    texto_col, area_col = st.columns([2, 1])
    texto = texto_col.text_input("Buscar por ID o nombre")
    area_fija = permisos.area_permitida(usuario)
    if area_fija:
        area_col.text_input("Área", area_fija, disabled=True)
        area = area_fija
    else:
        area = area_col.selectbox("Área", catalogos.AREAS, index=None, placeholder="Todas las áreas")

    resultados = talentos.buscar(usuario, texto, area)
    if not resultados:
        if texto.strip():
            st.warning(talentos.NO_IDENTIFICADO)
        else:
            st.info("No hay talentos registrados" + (f" en {area}." if area else "."))
        return

    tabla = pd.DataFrame([{
        "ID": fila["id_talento"],
        "Nombre": fila["nombre"],
        "Área": fila["area"],
        "Correo": fila["correo"],
        "Teléfono": fila["tel_mx"],
        "Fecha de ingreso": fecha(fila["fecha_ingreso"]),
        "Desempeño previo": fila["desempeno_previo"],
    } for fila in resultados])
    st.dataframe(tabla, hide_index=True, width="stretch")
    st.caption(f"{len(resultados)} talento(s).")

    por_id = {fila["id_talento"]: fila for fila in resultados}
    # Un talento elegido desde una notificación llega ya seleccionado
    preseleccion = st.session_state.pop("talentos_talento", None)
    if preseleccion in por_id:
        st.session_state["talentos_elegido"] = preseleccion
    id_elegido = st.selectbox(
        "Talento a " + ("modificar" if puede_editar else "consultar"), list(por_id), index=None,
        placeholder="Seleccione un talento", key="talentos_elegido",
        format_func=lambda id_talento: f"{id_talento} - {por_id[id_talento]['nombre']}")
    if id_elegido is None:
        return
    talento = talentos.obtener(usuario, id_elegido)
    if talento is None or not talento["activo"]:
        st.warning(talentos.NO_IDENTIFICADO)
        return
    vistas.encabezado_talento(talento, f"ID {talento['id_talento']} · {talento['area']}")
    pestana_datos, pestana_ia = st.tabs(["Datos del talento", "Evaluación con IA"])
    with pestana_datos:
        if puede_editar:
            with st.expander("Foto de perfil"):
                aviso = vistas.editor_foto(f"foto_talento_{talento['id_talento']}", talento["foto"],
                                           lambda foto: talentos.cambiar_foto(usuario, talento["id_talento"], foto))
                if aviso:
                    avisar(f"{aviso[:-1]} de {talento['nombre']}.")
            edicion(talento)
        else:
            ficha(talento)
    with pestana_ia:
        evaluacion_ia(talento)


def evaluacion_ia(talento):
    # Botón "Evaluar" solo para el Administrador (PRD, 6.7); ambos roles ven la última evaluación
    id_talento = talento["id_talento"]
    if puede_evaluar:
        estado = evaluaciones.estado(id_talento)
        disponibles = max(estado["limite"] - estado["usados"], 0)
        st.caption(f"Se evalúan los datos guardados del talento. Intentos disponibles hoy: {disponibles} "
                   f"de {estado['limite']} (se renuevan cada día o al modificar sus datos). Cada intento "
                   f"puede tardar hasta {estado['segundos']} segundos.")
        if st.button("Evaluar con IA", type="primary", disabled=disponibles == 0, key=f"evaluar_{id_talento}"):
            try:
                with st.spinner("Evaluando con IA, espere por favor..."):
                    resultado = evaluaciones.evaluar(usuario, id_talento)
            except errores.ErrorSistema as error:
                # Sin conexión con la IA se muestra la pantalla de error (PRD, 6.8)
                if error.codigo == "E-101":
                    raise
                st.session_state["error_ia"] = error.codigo
                st.rerun()
            avisar(f"Se evaluó a {talento['nombre']}: potencial {resultado['potencial_crecimiento_nivel']}, "
                   f"{resultado['puntuacion_talento_por_ia']} puntos.")
        codigo = st.session_state.pop("error_ia", None)
        if codigo:
            st.error(f"{errores.CATALOGO[codigo]} ({codigo})")
        if disponibles == 0 and codigo != "E-104":
            st.warning(f"{errores.CATALOGO['E-104']} (E-104)")

    evaluacion = evaluaciones.ultima(usuario, id_talento)
    if evaluacion is None:
        st.info("Este talento aún no tiene evaluaciones con IA.")
        return
    st.markdown(f"**Última evaluación:** {fecha(evaluacion['fecha_evaluacion'])}")
    potencial, puntuacion = st.columns(2)
    potencial.metric("Potencial de crecimiento", evaluacion["potencial_crecimiento_nivel"].capitalize())
    puntuacion.metric("Puntuación", evaluacion["puntuacion_talento_por_ia"])
    # La clasificación 9-box va como una fila más para que se lea completa
    filas = [{"Criterio": nombre, "Resultado": evaluacion[llave].capitalize()}
             for llave, nombre in CRITERIOS_IA.items()]
    filas.append({"Criterio": "Clasificación 9-box", "Resultado": evaluacion["clasificacion_9box"]})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.markdown("**Reporte**")
    st.write(evaluacion["reporte_ia"])


def bajas():
    registros = talentos.listar_bajas(usuario)
    if not registros:
        st.info("No hay talentos dados de baja.")
        return
    st.dataframe(pd.DataFrame([{
        "ID": fila["id_talento"],
        "Nombre": fila["nombre"],
        "Área": fila["area"],
        "Correo": fila["correo"],
        "Fecha de baja": fecha(fila["fecha_baja"]),
        "Motivo": fila["motivo_baja"],
    } for fila in registros]), hide_index=True, width="stretch")

    por_id = {fila["id_talento"]: fila for fila in registros}
    id_elegido = st.selectbox(
        "Talento a reactivar", list(por_id), index=None, placeholder="Seleccione un talento",
        format_func=lambda id_talento: f"{id_talento} - {por_id[id_talento]['nombre']}")
    if id_elegido is not None and st.button("Reactivar", type="primary"):
        talentos.reactivar(usuario, id_elegido)
        avisar(f"Se reactivó a {por_id[id_elegido]['nombre']}.")


st.title("Talentos")

aviso = st.session_state.pop("aviso_talentos", None)
if aviso:
    st.success(aviso)

if puede_editar:
    pestana_lista, pestana_nuevo, pestana_bajas = st.tabs(["Lista", "Nuevo talento", "Talentos dados de baja"])
    with pestana_lista:
        lista()
    with pestana_nuevo:
        alta()
    with pestana_bajas:
        bajas()
else:
    lista()
