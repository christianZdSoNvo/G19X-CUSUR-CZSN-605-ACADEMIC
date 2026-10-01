import streamlit as st

from backend import parametros, permisos, sesion

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "parametros")

st.title("Parámetros del sistema")
st.caption("Los cambios se aplican de inmediato y quedan registrados en la bitácora. "
           "El tiempo de inactividad se aplica a las sesiones que se inicien después del cambio.")

aviso = st.session_state.pop("aviso_parametros", None)
if aviso:
    st.success(aviso)

actuales = parametros.listar()
problemas = st.session_state.pop("problemas_parametros", {})

with st.form("parametros"):
    capturados = {}
    for grupo in parametros.GRUPOS:
        st.subheader(grupo)
        if grupo == "Contacto de soporte":
            st.caption(f'Si un dato se deja vacío, se muestra como "{parametros.POR_DEFINIR}".')
        for clave, (grupo_clave, etiqueta, tipo, minimo, maximo) in parametros.PARAMETROS.items():
            if grupo_clave != grupo:
                continue
            fila = actuales.get(clave, {})
            valor = fila.get("valor", "")
            if tipo == "entero":
                capturados[clave] = st.number_input(
                    etiqueta, min_value=minimo, max_value=maximo, step=1,
                    value=min(max(int(valor), minimo), maximo) if valor.isdigit() else minimo,
                    help=f"De {minimo} a {maximo}.",
                )
            else:
                capturados[clave] = st.text_input(etiqueta, valor if parametros.definido(valor) else "",
                                                  max_chars=maximo, placeholder=parametros.POR_DEFINIR)
            if clave in problemas:
                st.error(problemas[clave])
            if fila.get("modifico"):
                st.caption(f"Modificado por {fila['modifico']} el {fila['fecha_modificacion']:%d/%m/%Y %H:%M}.")
    guardar = st.form_submit_button("Guardar", type="primary")

if guardar:
    problemas, cambiados = parametros.guardar(usuario, capturados)
    if problemas:
        st.session_state["problemas_parametros"] = problemas
    else:
        if "minutos_inactividad_sesion" in cambiados:
            usuario["minutos_inactividad"] = int(capturados["minutos_inactividad_sesion"])
        st.session_state["aviso_parametros"] = (
            f"Se guardaron {len(cambiados)} cambio(s)." if cambiados else "No hubo cambios que guardar.")
    st.rerun()
