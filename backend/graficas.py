import datetime
import math

import plotly.graph_objects as go
import streamlit as st

from backend import analitica, evaluaciones

# Figuras de Plotly para paneles e historial, con los colores del tema (azul oscuro,
# dorado y rojo; grises de apoyo). En el tema oscuro el azul y el rojo se aclaran
# para que se vean sobre el fondo, igual que en .streamlit/config.toml.

PALETAS = {
    "light": {"alto": "#0B1F3A", "medio": "#C9A227", "bajo": "#B22234", "linea": "#0B1F3A",
              "evento": "#B22234", "vacio": "#F2F3F5", "texto": "#0B1F3A", "texto_lleno": "#FFFFFF"},
    "dark": {"alto": "#5B7DB1", "medio": "#C9A227", "bajo": "#D64550", "linea": "#E3C565",
             "evento": "#D64550", "vacio": "#13233D", "texto": "#F4F1E8", "texto_lleno": "#0A1628"},
}
NOMBRE_NIVEL = {"bajo": "Bajo", "medio": "Medio", "alto": "Alto"}
# Posición de cada clasificación en la matriz 9-box: (desempeño, potencial)
POSICION_9BOX = {nombre: (desempeno, potencial)
                 for (potencial, desempeno), nombre in evaluaciones.MATRIZ_9BOX.items()}


def paleta():
    return PALETAS["dark" if st.context.theme.type == "dark" else "light"]


def _transparente(color, opacidad=0.2):
    # "#RRGGBB" -> "rgba(r, g, b, opacidad)" para rellenar sin apagar el color de la línea
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {opacidad})"


def _eje_conteo(titulo, maximo):
    # Eje de número de talentos: solo enteros (sin 0.5, 1.5, ...)
    return {"title": titulo, "rangemode": "tozero", "dtick": max(1, math.ceil(maximo / 6))}


def _ajustar(figura, alto=360, **ejes):
    figura.update_layout(height=alto, margin={"l": 60, "r": 20, "t": 30, "b": 50},
                         legend={"orientation": "h", "y": -0.15}, **ejes)
    return figura


def distribucion(tabla):
    # Barras apiladas por área con el número de talentos de cada nivel
    colores = paleta()
    figura = go.Figure([
        go.Bar(name=NOMBRE_NIVEL[nivel], x=list(tabla.index), y=list(tabla[nivel]), marker_color=colores[nivel],
               hovertemplate="%{x}<br>" + NOMBRE_NIVEL[nivel] + ": %{y}<extra></extra>")
        for nivel in analitica.NIVELES
    ])
    return _ajustar(figura, barmode="stack", yaxis=_eje_conteo("Talentos", tabla.sum(axis=1).max()))


def barras_nivel(conteo):
    # Desglose de un área por nivel de potencial (drill-down)
    colores = paleta()
    niveles = list(analitica.NIVELES)
    figura = go.Figure(go.Bar(
        x=[NOMBRE_NIVEL[nivel] for nivel in niveles], y=[int(conteo.get(nivel, 0)) for nivel in niveles],
        customdata=niveles, marker_color=[colores[nivel] for nivel in niveles],
        hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    return _ajustar(figura, yaxis=_eje_conteo("Talentos", max(conteo.values, default=0)), showlegend=False)


def matriz_9box(conteo):
    # Cuadrícula 3×3: un mapa de calor dibuja las celdas y encima van puntos invisibles,
    # porque la selección con clic de Streamlit funciona con puntos y no con mapas de calor
    colores = paleta()
    niveles = list(analitica.NIVELES)
    nombres = [[evaluaciones.MATRIZ_9BOX[(potencial, desempeno)] for desempeno in niveles] for potencial in niveles]
    figura = go.Figure(go.Heatmap(
        x=niveles, y=niveles, z=[[conteo[nombre] for nombre in fila] for fila in nombres], text=nombres,
        texttemplate="<b>%{z}</b><br>%{text}", textfont={"size": 13},
        colorscale=[[0, colores["vacio"]], [1, colores["medio"]]], zmin=0, zmax=max(max(conteo.values()), 1),
        showscale=False, xgap=6, ygap=6, hoverinfo="skip",
    ))
    celdas = list(POSICION_9BOX)
    figura.add_trace(go.Scatter(
        x=[POSICION_9BOX[nombre][0] for nombre in celdas], y=[POSICION_9BOX[nombre][1] for nombre in celdas],
        mode="markers", customdata=celdas, marker={"size": 70, "opacity": 0},
        text=[conteo[nombre] for nombre in celdas], hovertemplate="%{customdata}: %{text} talento(s)<extra></extra>",
    ))
    # Rango fijo y sin zoom: con el ajuste automático, el margen para los puntos
    # invisibles encogía la cuadrícula cada vez que se hacía clic en una celda
    ejes = {"type": "category", "categoryorder": "array", "categoryarray": niveles, "range": [-0.5, 2.5],
            "autorange": False, "fixedrange": True, "tickvals": niveles,
            "ticktext": [NOMBRE_NIVEL[nivel] for nivel in niveles], "showgrid": False, "zeroline": False}
    return _ajustar(figura, alto=400, showlegend=False, xaxis={**ejes, "title": "Desempeño previo"},
                    yaxis={**ejes, "title": "Potencial de crecimiento"})


def promedio_por_area(promedios):
    figura = go.Figure(go.Bar(
        x=list(promedios.values), y=list(promedios.index), orientation="h", marker_color=paleta()["alto"],
        text=list(promedios.values), textposition="auto", hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    return _ajustar(figura, xaxis={"title": "Puntuación promedio", "range": [0, 100]}, showlegend=False)


def histograma(conteo):
    figura = go.Figure(go.Bar(
        x=list(conteo.index), y=list(conteo.values), marker_color=paleta()["medio"],
        hovertemplate="%{x} puntos: %{y} talento(s)<extra></extra>",
    ))
    return _ajustar(figura, xaxis_title="Puntuación de IA", yaxis=_eje_conteo("Talentos", conteo.max()),
                    bargap=0.05, showlegend=False)


def evolucion(promedios):
    figura = go.Figure(go.Scatter(
        x=list(promedios.index), y=list(promedios.values), mode="lines+markers",
        line={"color": paleta()["linea"], "width": 3}, hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    return _ajustar(figura, xaxis={"title": "Mes", "type": "category"},
                    yaxis={"title": "Puntuación promedio", "range": [0, 100]}, showlegend=False)


def radar(talentos):
    # talentos: lista de (nombre, {criterio: 1-3}); hasta 5 (PRD, 13.1)
    colores = paleta()
    serie = [colores["alto"], colores["medio"], colores["bajo"], "#5B6B82", "#9AA4B2"]
    figura = go.Figure()
    for indice, (nombre, valores) in enumerate(talentos):
        criterios = list(valores)
        figura.add_trace(go.Scatterpolar(
            r=[*valores.values(), next(iter(valores.values()))], theta=[*criterios, criterios[0]],
            name=nombre, line={"color": serie[indice % len(serie)], "width": 2}, fill="toself",
            fillcolor=_transparente(serie[indice % len(serie)]),
        ))
    return _ajustar(figura, alto=420, polar={"radialaxis": {
        "range": [0, 3], "tickvals": [1, 2, 3], "ticktext": ["Bajo", "Medio", "Alto"]}})


def linea_de_tiempo(fecha_ingreso, evaluaciones, eventos):
    # Puntuación de IA en el tiempo (eje vertical) con los eventos marcados (PRD, 9.10 y 13.3)
    colores = paleta()
    figura = go.Figure()
    figura.add_trace(go.Scatter(
        x=[fila["fecha_evaluacion"] for fila in evaluaciones],
        y=[fila["puntuacion_talento_por_ia"] for fila in evaluaciones],
        mode="lines+markers", name="Puntuación de IA",
        line={"color": colores["linea"], "width": 3}, marker={"size": 10},
        customdata=[[NOMBRE_NIVEL[fila["potencial_crecimiento_nivel"]], fila["clasificacion_9box"]]
                    for fila in evaluaciones],
        hovertemplate="%{x|%d/%m/%Y}<br>Puntuación: %{y}<br>Potencial: %{customdata[0]}"
                      "<br>%{customdata[1]}<extra></extra>",
    ))
    if eventos:
        figura.add_trace(go.Scatter(
            x=[evento["fecha_evento"] for evento in eventos], y=[0] * len(eventos),
            mode="markers", name="Eventos", marker={"symbol": "diamond", "size": 12, "color": colores["evento"]},
            customdata=[f"{analitica.TIPOS_EVENTO[evento['tipo_evento']]}: {evento['descripcion']}"
                        for evento in eventos],
            hovertemplate="%{x|%d/%m/%Y}<br>%{customdata}<extra></extra>",
        ))
    return _ajustar(figura, alto=400,
                    xaxis={"title": "Fecha", "range": [fecha_ingreso - datetime.timedelta(days=15),
                                                       datetime.date.today() + datetime.timedelta(days=15)],
                           "tickformat": "%d/%m/%Y"},
                    yaxis={"title": "Puntuación de IA", "range": [-5, 105]})
