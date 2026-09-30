import pandas as pd
import streamlit as st

from backend import analitica, graficas

# Vistas compartidas entre páginas (historial en su página y en el drill-down de paneles)


def fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


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
