import datetime
import json

import pandas as pd
import streamlit as st

from backend import bitacora, permisos, sesion, usuarios

usuario = sesion.usuario_actual()
permisos.exigir(usuario, "bitacora")

st.set_page_config(layout="wide")
st.title("Bitácora")
st.caption("Registro de las acciones del sistema (PRD, 8.5). Solo consulta: no se puede editar ni borrar.")


def detalle_legible(texto):
    # El detalle se guarda como JSON; se muestra como "clave: valor; ..."
    if not texto:
        return ""
    try:
        datos = json.loads(texto)
    except ValueError:
        return texto
    if not isinstance(datos, dict):
        return str(datos)
    return "; ".join(f"{clave}: {valor}" for clave, valor in datos.items())


hoy = datetime.date.today()
personas = {fila["id_usuario"]: f"{fila['nombre']} ({fila['usuario']})" for fila in usuarios.listar()}
personas[bitacora.SIN_USUARIO] = "Sin usuario (intentos con un usuario inexistente)"

fechas_col, usuario_col = st.columns(2)
fechas = fechas_col.date_input("Fechas", (hoy - datetime.timedelta(days=7), hoy), max_value=hoy,
                               format="DD/MM/YYYY")
id_usuario = usuario_col.selectbox("Usuario", list(personas), index=None, format_func=personas.get,
                                   placeholder="Todos los usuarios")
acciones_col, tabla_col = st.columns(2)
acciones = acciones_col.multiselect("Acción", list(bitacora.ACCIONES), format_func=bitacora.ACCIONES.get,
                                    placeholder="Todas las acciones")
tabla = tabla_col.selectbox("Tabla afectada", bitacora.tablas(usuario), index=None, placeholder="Todas las tablas")

if len(fechas) != 2:
    st.info("Seleccione la fecha final del periodo.")
    st.stop()

filas = bitacora.consultar(usuario, fechas[0], fechas[1], id_usuario, acciones, tabla)
if not filas:
    st.info("No hay registros con esos filtros.")
    st.stop()

if len(filas) > bitacora.MAX_FILAS:
    filas = filas[:bitacora.MAX_FILAS]
    st.warning(f"Se muestran los {bitacora.MAX_FILAS:,} registros más recientes; acote los filtros para ver el resto.")
else:
    st.caption(f"{len(filas):,} registro(s).")

st.dataframe(pd.DataFrame([{
    "Fecha y hora": fila["fecha_hora"].strftime("%d/%m/%Y %H:%M:%S"),
    "Usuario": f"{fila['nombre']} ({fila['usuario']})" if fila["id_usuario"] else "Sin usuario",
    "Acción": bitacora.ACCIONES[fila["accion"]],
    "Tabla": fila["tabla_afectada"] or "",
    "ID del registro": fila["id_registro_afectado"],
    "Detalle": detalle_legible(fila["detalle"]),
} for fila in filas]), hide_index=True, width="stretch", height=560)
