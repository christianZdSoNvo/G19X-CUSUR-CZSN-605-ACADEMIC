import datetime
import json

import httpx
import pytest

from backend import db, errores, evaluaciones, ia, permisos, talentos

VALIDA = {
    "desempeno_pre_ev": "alto", "resultados_cap_ev": "medio", "experiencia_lab_ev": "alto",
    "objetivos_fut_ev": "medio", "competencias_ev": "alto", "liderazgo_prev_ev": "bajo",
    "potencial_crecimiento_nivel": "alto", "puntuacion_talento_por_ia": 85,
    "reporte_ia": "Ana García muestra un desempeño sobresaliente.",
}
TALENTO = {"nombre": "Ana García", "area": "Calidad", "correo": "ana.pytest@ejemplo.com",
           "tel_mx": "5587654321", "fecha_ingreso": datetime.date(2023, 5, 2), "desempeno_previo": 80,
           "competencias": "Comunicación", "capacitacion": "Scrum", "experiencia": "5 años",
           "objetivos_futuros": "Liderar un equipo", "liderazgo_previo": ""}


def _json(**cambios):
    return json.dumps({**VALIDA, **cambios}, ensure_ascii=False)


# --- Validación de la respuesta, prompt y 9-box (sin BD ni modelo) ---

def test_respuesta_valida():
    evaluacion, motivo = ia.validar_respuesta(_json(competencias_ev=" ALTO ", puntuacion_talento_por_ia=85.0))
    assert motivo is None
    assert evaluacion["competencias_ev"] == "alto"
    assert evaluacion["puntuacion_talento_por_ia"] == 85


@pytest.mark.parametrize("texto", [
    "no es json",
    "[1, 2]",
    json.dumps({llave: valor for llave, valor in VALIDA.items() if llave != "reporte_ia"}),
    _json(extra="sobra"),
    _json(liderazgo_prev_ev="regular"),
    _json(puntuacion_talento_por_ia=101),
    _json(puntuacion_talento_por_ia=85.5),
    _json(puntuacion_talento_por_ia="85"),
    _json(puntuacion_talento_por_ia=True),
    _json(puntuacion_talento_por_ia=45),  # alto con 45: fuera del rango del nivel
    _json(reporte_ia="x" * 1001),
    _json(reporte_ia="   "),
])
def test_respuestas_invalidas(texto):
    evaluacion, motivo = ia.validar_respuesta(texto)
    assert evaluacion is None and motivo


@pytest.mark.parametrize("puntuacion, nivel", [(0, "bajo"), (30, "bajo"), (31, "medio"), (70, "medio"),
                                               (71, "alto"), (100, "alto")])
def test_rangos(puntuacion, nivel):
    assert ia.nivel_de_puntuacion(puntuacion) == nivel


@pytest.mark.parametrize("desempeno, potencial, esperado", [
    (80, "alto", "Alta estrella"),
    (20, "alto", "Diamante en bruto"),
    (50, "medio", "Colaborador sólido"),
    (71, "bajo", "Especialista confiable"),
    (31, "bajo", "Colaborador efectivo"),
    (None, "alto", evaluaciones.SIN_CLASIFICAR),
])
def test_9box(desempeno, potencial, esperado):
    assert evaluaciones.clasificar_9box(desempeno, potencial) == esperado


def test_prompt_sin_datos_de_contacto():
    prompt = ia.construir_prompt({**TALENTO, "desempeno_previo": None})
    assert "Nombre: Ana García" in prompt and "Desempeño previo: Sin registro" in prompt
    assert TALENTO["correo"] not in prompt and TALENTO["tel_mx"] not in prompt
    assert ia.REINTENTO not in prompt
    assert ia.REINTENTO in ia.construir_prompt(TALENTO, reintento=True)


# --- Flujo completo con MySQL (sin dejar rastro) y el modelo simulado ---

@pytest.fixture
def modelo(monkeypatch):
    # Cola de respuestas del modelo simulado: texto o excepción; guarda los prompts recibidos
    simulado = {"respuestas": [], "prompts": []}

    def pedir(prompt, segundos):
        simulado["prompts"].append(prompt)
        respuesta = simulado["respuestas"].pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(ia, "pedir_evaluacion", pedir)
    monkeypatch.setattr(ia, "asegurar_carga", lambda: None)
    return simulado


@pytest.fixture
def talento(administrador):
    _, id_talento = talentos.crear(administrador, TALENTO)
    return id_talento


def _eventos(id_talento):
    with db.transaccion() as cursor:
        cursor.execute("SELECT tipo_evento FROM Eventos_talento WHERE id_talento = %s ORDER BY id_evento",
                       (id_talento,))
        return [fila["tipo_evento"] for fila in cursor.fetchall()]


def _codigo(administrador, id_talento):
    with pytest.raises(errores.ErrorSistema) as error:
        evaluaciones.evaluar(administrador, id_talento)
    return error.value.codigo


def test_evaluacion_valida(administrador, talento, modelo):
    modelo["respuestas"] = [_json()]
    resultado = evaluaciones.evaluar(administrador, talento)
    assert resultado["clasificacion_9box"] == "Alta estrella"
    guardada = evaluaciones.ultima(administrador, talento)
    assert guardada["puntuacion_talento_por_ia"] == 85 and guardada["fecha_evaluacion"] == datetime.date.today()
    assert _eventos(talento) == ["ingreso", "evaluacion_ia"]
    assert evaluaciones.estado(talento)["usados"] == 1

    # Si cambia el nivel de potencial se registra cambio_clasificacion
    modelo["respuestas"] = [_json(potencial_crecimiento_nivel="medio", puntuacion_talento_por_ia=60)]
    assert evaluaciones.evaluar(administrador, talento)["clasificacion_9box"] == "Profesional clave"
    assert _eventos(talento) == ["ingreso", "evaluacion_ia", "evaluacion_ia", "cambio_clasificacion"]


def test_reintento_y_limite(administrador, talento, modelo):
    # Primera respuesta inválida: se reintenta con la indicación del PRD y la segunda vale
    modelo["respuestas"] = [_json(puntuacion_talento_por_ia=45), _json()]
    evaluaciones.evaluar(administrador, talento)
    assert ia.REINTENTO not in modelo["prompts"][0] and ia.REINTENTO in modelo["prompts"][1]
    assert evaluaciones.estado(talento)["usados"] == 2

    # Queda 1 intento: la respuesta inválida lo agota (E-103) y el siguiente clic da E-104
    modelo["respuestas"] = ["no es json"]
    assert _codigo(administrador, talento) == "E-103"
    assert _codigo(administrador, talento) == "E-104"

    # Al modificar el registro del talento se renuevan los intentos (PRD, 10)
    assert talentos.editar(administrador, talento, {**TALENTO, "nombre": "Ana María García"}) == {}
    assert evaluaciones.estado(talento)["usados"] == 0


def test_errores_de_conexion_y_tiempo(administrador, talento, modelo):
    # Sin conexión con Ollama: E-101 y no se gasta el intento
    modelo["respuestas"] = [ConnectionError("Ollama apagado")]
    assert _codigo(administrador, talento) == "E-101"
    assert evaluaciones.estado(talento)["usados"] == 0

    # Tiempo agotado: E-102 y sí cuenta como intento
    modelo["respuestas"] = [httpx.ReadTimeout("90 s")]
    assert _codigo(administrador, talento) == "E-102"
    assert evaluaciones.estado(talento)["usados"] == 1
    assert evaluaciones.ultima(administrador, talento) is None


def test_encargado_no_evalua(administrador, talento, modelo):
    encargado = {**administrador, "cargo": permisos.ENCARGADO, "area": "Calidad"}
    assert _codigo(encargado, talento) == "E-304"
    assert modelo["prompts"] == []


def test_pantalla_de_evaluacion(administrador, talento, modelo, app_con_sesion):
    modelo["respuestas"] = [_json()]
    app = app_con_sesion(administrador).run()
    app.switch_page("paginas/talentos.py").run()
    app.text_input[0].input(str(talento)).run()
    app.selectbox[1].select(talento).run()
    assert "Este talento aún no tiene evaluaciones con IA." in [info.value for info in app.info]
    app.button(key=f"evaluar_{talento}").click().run()
    assert not app.exception
    assert app.success[0].value == "Se evaluó a Ana García: potencial alto, 85 puntos."
    assert [metrica.value for metrica in app.metric] == ["Alto", "85"]
    # La tabla de criterios termina con la 9-box (puede haber otras tablas, p. ej. las bajas)
    assert ["Clasificación 9-box", "Alta estrella"] in [tabla.value.iloc[-1].tolist() for tabla in app.dataframe]

    # El Encargado ve la evaluación, pero no el botón
    encargado = {**administrador, "cargo": permisos.ENCARGADO, "area": "Calidad"}
    app = app_con_sesion(encargado).run()
    app.switch_page("paginas/talentos.py").run()
    app.selectbox[0].select(talento).run()
    assert not app.exception
    assert f"evaluar_{talento}" not in [boton.key for boton in app.button]
    assert [metrica.value for metrica in app.metric] == ["Alto", "85"]
    # La tabla de criterios termina con la 9-box (puede haber otras tablas, p. ej. las bajas)
    assert ["Clasificación 9-box", "Alta estrella"] in [tabla.value.iloc[-1].tolist() for tabla in app.dataframe]
