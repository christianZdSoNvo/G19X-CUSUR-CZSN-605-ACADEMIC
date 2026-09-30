import datetime
import json

import pandas as pd
import pytest

from backend import analitica, evaluaciones, graficas, ia, permisos, talentos

HOY = datetime.date(2026, 9, 29)


def _fila(id_talento, area, nivel=None, puntuacion=None, clasificacion=None, fecha=None, ingreso=(2020, 1, 1)):
    criterios = {llave: nivel for llave in ia.CRITERIOS}
    return {"id_talento": id_talento, "nombre": f"Talento {id_talento}", "area": area,
            "fecha_ingreso": datetime.date(*ingreso), "desempeno_previo": 50,
            "id_evaluacion": id_talento if nivel else None, "fecha_evaluacion": fecha,
            "puntuacion_talento_por_ia": puntuacion, "potencial_crecimiento_nivel": nivel,
            "clasificacion_9box": clasificacion, **criterios}


@pytest.fixture
def datos():
    return pd.DataFrame([
        _fila(1, "Calidad", "alto", 85, "Futuro líder", datetime.date(2026, 9, 10)),
        _fila(2, "Calidad", "medio", 50, "Colaborador sólido", datetime.date(2026, 8, 5), ingreso=(2025, 6, 1)),
        _fila(3, "Finanzas", "bajo", 20, "Colaborador efectivo", datetime.date(2026, 9, 2)),
        _fila(4, "Finanzas", "alto", 100, "Futuro líder", datetime.date(2026, 7, 1)),
        _fila(5, "Finanzas"),  # sin evaluar
    ])


@pytest.fixture
def todas():
    return pd.DataFrame([
        {"id_talento": 1, "fecha_evaluacion": datetime.date(2026, 8, 20), "puntuacion_talento_por_ia": 65},
        {"id_talento": 1, "fecha_evaluacion": datetime.date(2026, 9, 10), "puntuacion_talento_por_ia": 85},
        {"id_talento": 2, "fecha_evaluacion": datetime.date(2026, 8, 5), "puntuacion_talento_por_ia": 50},
        {"id_talento": 3, "fecha_evaluacion": datetime.date(2026, 9, 2), "puntuacion_talento_por_ia": 20},
        {"id_talento": 4, "fecha_evaluacion": datetime.date(2026, 7, 1), "puntuacion_talento_por_ia": 100},
    ])


def _ids(tabla):
    return sorted(tabla["id_talento"])


def test_filtros(datos):
    assert _ids(analitica.filtrar(datos)) == [1, 2, 3, 4, 5]
    assert _ids(analitica.filtrar(datos, area="Finanzas")) == [3, 4, 5]
    # Los filtros de evaluación dejan fuera a los talentos sin evaluar
    assert _ids(analitica.filtrar(datos, niveles=["alto"])) == [1, 4]
    assert _ids(analitica.filtrar(datos, clasificaciones=["Colaborador sólido"])) == [2]
    assert _ids(analitica.filtrar(datos, puntuacion=(0, 100))) == [1, 2, 3, 4]
    assert _ids(analitica.filtrar(datos, puntuacion=(50, 90))) == [1, 2]
    assert _ids(analitica.filtrar(datos, fechas=(datetime.date(2026, 9, 1), datetime.date(2026, 9, 30)))) == [1, 3]
    assert _ids(analitica.filtrar(datos, antiguedad=(0, 2), hoy=HOY)) == [2]
    assert _ids(analitica.filtrar(datos, area="Finanzas", niveles=["alto", "bajo"])) == [3, 4]


def test_indicadores(datos, todas):
    assert analitica.indicadores(datos, todas, hoy=HOY) == {
        "total": 5, "porcentaje_alto": 50.0, "evaluaciones_mes": 2, "sin_evaluar": 1}
    solo_sin_evaluar = datos[datos["id_talento"] == 5]
    assert analitica.indicadores(solo_sin_evaluar, todas, hoy=HOY)["porcentaje_alto"] is None


def test_distribucion_y_9box(datos):
    tabla = analitica.distribucion_por_area(datos)
    assert list(tabla.columns) == ["bajo", "medio", "alto"]
    assert tabla.loc["Calidad"].tolist() == [0, 1, 1]
    assert tabla.loc["Finanzas"].tolist() == [1, 0, 1]
    conteo = analitica.conteo_9box(datos)
    assert len(conteo) == 10 and conteo["Futuro líder"] == 2 and conteo["Alta estrella"] == 0


def test_promedios_histograma_y_evolucion(datos, todas):
    assert analitica.promedio_por_area(datos).to_dict() == {"Calidad": 67.5, "Finanzas": 60.0}
    conteo = analitica.histograma(datos)
    assert conteo["20-29"] == 1 and conteo["50-59"] == 1 and conteo["80-89"] == 1
    assert conteo["90-100"] == 1  # el 100 entra en el último rango
    assert conteo.sum() == 4
    assert analitica.evolucion_mensual(datos, todas).to_dict() == {"2026-07": 100.0, "2026-08": 57.5,
                                                                    "2026-09": 52.5}
    solo_septiembre = (datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
    assert analitica.evolucion_mensual(datos, todas, solo_septiembre).to_dict() == {"2026-09": 52.5}


def test_radar(datos):
    fila = datos.iloc[0]
    assert analitica.valores_radar(fila) == dict.fromkeys(analitica.NOMBRES_CRITERIOS.values(), 3)


def test_figuras(datos, todas):
    # Las figuras se construyen sin errores (paleta clara, fuera de Streamlit)
    assert graficas.distribucion(analitica.distribucion_por_area(datos)).data
    assert len(graficas.matriz_9box(analitica.conteo_9box(datos)).data[1].x) == 9
    assert graficas.radar([("A", analitica.valores_radar(datos.iloc[0]))]).data
    assert graficas.linea_de_tiempo(datetime.date(2020, 1, 1), [], []).data


# --- Páginas con MySQL (sin dejar rastro) ---

TALENTO = {"nombre": "Paula Ríos", "area": "Calidad", "correo": "paula.pytest@ejemplo.com",
           "tel_mx": "5511112222", "fecha_ingreso": datetime.date(2022, 1, 10), "desempeno_previo": 75,
           "competencias": "", "capacitacion": "", "experiencia": "", "objetivos_futuros": "",
           "liderazgo_previo": ""}
RESPUESTA = {**dict.fromkeys(ia.CRITERIOS, "alto"), "potencial_crecimiento_nivel": "alto",
             "puntuacion_talento_por_ia": 88, "reporte_ia": "Paula Ríos tiene un gran potencial."}


@pytest.fixture
def evaluado(administrador, monkeypatch):
    monkeypatch.setattr(ia, "asegurar_carga", lambda: None)
    monkeypatch.setattr(ia, "pedir_evaluacion", lambda prompt, segundos: json.dumps(RESPUESTA))
    _, id_talento = talentos.crear(administrador, TALENTO)
    evaluaciones.evaluar(administrador, id_talento)
    return id_talento


def test_consultas_por_area(administrador, evaluado):
    fila = analitica.talentos_con_ultima_evaluacion(administrador).set_index("id_talento").loc[evaluado]
    assert fila["puntuacion_talento_por_ia"] == 88 and fila["clasificacion_9box"] == "Alta estrella"
    encargado = {**administrador, "cargo": permisos.ENCARGADO, "area": "Finanzas"}
    assert evaluado not in set(analitica.talentos_con_ultima_evaluacion(encargado)["id_talento"])
    assert evaluado not in set(analitica.todas_las_evaluaciones(encargado)["id_talento"])
    historial = analitica.historial(administrador, evaluado)
    assert [evento["tipo_evento"] for evento in historial["eventos"]] == ["ingreso", "evaluacion_ia"]
    assert len(historial["evaluaciones"]) == 1


def test_pagina_de_paneles(administrador, evaluado, app_con_sesion):
    for usuario in (administrador, {**administrador, "cargo": permisos.ENCARGADO, "area": "Calidad"}):
        app = app_con_sesion(usuario).run()
        app.switch_page("paginas/paneles.py").run()
        assert not app.exception
        assert [metrica.label for metrica in app.metric] == [
            "Talentos activos", "Con potencial alto", "Evaluaciones del mes", "Talentos sin evaluar"]

    # Drill-down: con un grupo elegido aparece la lista de sus talentos
    app.session_state["panel_seleccion"] = {"celda": "Alta estrella"}
    app.run()
    assert not app.exception
    assert app.subheader[0].value == "Talentos en \"Alta estrella\""
    assert evaluado in app.dataframe[0].value["ID"].tolist()


def test_pagina_de_historial(administrador, evaluado, app_con_sesion):
    app = app_con_sesion(administrador).run()
    app.session_state["historial_talento"] = evaluado
    app.switch_page("paginas/historial.py").run()
    assert not app.exception
    assert app.subheader[0].value == TALENTO["nombre"]
    tipos = app.dataframe[-1].value["Tipo"].tolist()
    assert tipos == ["Evaluación con IA", "Ingreso"]
