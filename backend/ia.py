"""Conexión con Ollama (modelo de IA local) y armado y validación de la evaluación (PRD, 10)."""

import json
import threading
import time

import ollama

from backend import config, errores

NIVELES = ("bajo", "medio", "alto")
# Rangos de puntuación de cada nivel de potencial (PRD, 10)
RANGOS = {"bajo": (0, 30), "medio": (31, 70), "alto": (71, 100)}
CRITERIOS = ("desempeno_pre_ev", "resultados_cap_ev", "experiencia_lab_ev", "objetivos_fut_ev",
             "competencias_ev", "liderazgo_prev_ev")
LLAVES = (*CRITERIOS, "potencial_crecimiento_nivel", "puntuacion_talento_por_ia", "reporte_ia")
# Al modelo se le piden hasta 1000 caracteres. No puede contarlos con exactitud, así que
# no hay mínimo y se aceptan hasta 1200 como margen; si aun así llega al límite del
# esquema (que corta el texto), se recorta en la última oración completa.
MAX_REPORTE = 1200
# Tiempo que Ollama conserva el modelo en memoria tras la última llamada
MANTENER_CARGADO = "30m"

# Esquema para el parámetro "format" de Ollama: obliga al modelo a respetar la estructura
ESQUEMA = {
    "type": "object",
    "properties": {
        **{llave: {"type": "string", "enum": list(NIVELES)} for llave in (*CRITERIOS, "potencial_crecimiento_nivel")},
        "puntuacion_talento_por_ia": {"type": "integer", "minimum": 0, "maximum": 100},
        "reporte_ia": {"type": "string", "maxLength": MAX_REPORTE},
    },
    "required": list(LLAVES),
    "additionalProperties": False,
}

PROMPT = """Eres un agente evaluador de talento humano.
Tu tarea es analizar perfiles de empleados según criterios definidos.
Evalúa cada criterio con un nivel: alto, medio o bajo (en minúsculas), exceptuando los criterios reporte y puntuación.
En el criterio reporte, genera un texto donde se comience por el nombre del talento, siguiendo por su evaluación general explicada en un texto, en el que menciones razones y porque de sus evaluaciones. Termina el reporte con una sugerencia sobre acciones y proyectos que se pueden aplicar al talento. El texto puede tener hasta 1000 caracteres, todo se trabajará en el idioma español latino.
En el criterio puntuación, asigna una nota de 0 a 100 que corresponda al nivel que diste en potencial de crecimiento (bajo -> 0 - 30, medio -> 31 – 70, alto -> 71 – 100). La nota va en su propia llave, no dentro del reporte.
Devuelve únicamente un objeto JSON, sin texto adicional, con exactamente estas llaves:
{
  "desempeno_pre_ev": "alto | medio | bajo",
  "resultados_cap_ev": "alto | medio | bajo",
  "experiencia_lab_ev": "alto | medio | bajo",
  "objetivos_fut_ev": "alto | medio | bajo",
  "competencias_ev": "alto | medio | bajo",
  "liderazgo_prev_ev": "alto | medio | bajo",
  "potencial_crecimiento_nivel": "alto | medio | bajo",
  "puntuacion_talento_por_ia": número entero de 0 a 100,
  "reporte_ia": "texto de hasta 1000 caracteres"
}

Criterios de evaluación:
- Desempeño previo (logros alcanzados, cumplimiento de metas, calidad de entregables, etc.).
- Resultados de capacitación (certificaciones obtenidas, calificaciones en cursos, participación, etc.).
- Experiencia laboral (años de experiencia, roles desempeñados, proyectos relevantes, etc.).
- Objetivos futuros (planes de desarrollo profesional, disposición a asumir reto, etc.).
- Competencias (cualidades personales y sociales)
- Liderazgo previo (experiencias liderando equipos, influencia positiva, toma de decisiones, etc.).
- Potencial de crecimiento (Dar un valor general entre Alto, Medio y Bajo según la evaluación de los criterios previos)
- Reporte (Texto explicativo con evaluación general, razones de las calificaciones, y sugerencias de trayectorias, riesgos y acciones de desarrollo).
"""

REINTENTO = ("Tu respuesta anterior no respetó el formato. Devuelve únicamente el objeto JSON con las 9 llaves "
             "indicadas, sus valores permitidos y una puntuación dentro del rango del nivel de potencial")


def obtener_cliente(timeout=None):
    """Crea un cliente de Ollama con la dirección del archivo .env."""
    return ollama.Client(host=config.OLLAMA_HOST, timeout=timeout)


def probar_conexion():
    """Comprueba que Ollama responde y si el modelo configurado está descargado.

    Devuelve (modelos_instalados, modelo_disponible).
    """
    respuesta = obtener_cliente().list()
    modelos = [m.model for m in respuesta.models]
    return modelos, config.OLLAMA_MODEL in modelos


def construir_prompt(talento, reintento=False):
    # Solo el nombre y los criterios; nunca el correo ni el teléfono (PRD, 8.1)
    desempeno = talento["desempeno_previo"]
    perfil = (
        "\nPerfil a evaluar:\n"
        f"Nombre: {talento['nombre']}\n"
        f"Desempeño previo: {'Sin registro' if desempeno is None else f'{desempeno} de 100'}\n"
        f"Resultados de capacitación: {talento['capacitacion']}\n"
        f"Experiencia laboral: {talento['experiencia']}\n"
        f"Objetivos futuros: {talento['objetivos_futuros']}\n"
        f"Competencias: {talento['competencias']}\n"
        f"Liderazgo previo: {talento['liderazgo_previo']}\n"
    )
    return PROMPT + perfil + (f"\n{REINTENTO}\n" if reintento else "")


def nivel_de_puntuacion(puntuacion):
    for nivel, (minimo, maximo) in RANGOS.items():
        if minimo <= puntuacion <= maximo:
            return nivel
    return None


def recortar_reporte(reporte):
    # El esquema corta el reporte en MAX_REPORTE caracteres, a veces a media frase: se
    # conserva hasta la última oración completa (si queda al menos la mitad del texto)
    fin = reporte[:MAX_REPORTE].rfind(".")
    return reporte[:fin + 1] if fin >= MAX_REPORTE // 2 else reporte


def validar_respuesta(texto):
    # Devuelve (evaluación lista para guardar, None) o (None, motivo del rechazo)
    try:
        datos = json.loads(texto)
    except (TypeError, json.JSONDecodeError):
        return None, "no es JSON"
    if not isinstance(datos, dict) or set(datos) != set(LLAVES):
        return None, "llaves distintas a las 9 esperadas"

    evaluacion = {}
    for llave in (*CRITERIOS, "potencial_crecimiento_nivel"):
        nivel = datos[llave].strip().lower() if isinstance(datos[llave], str) else None
        if nivel not in NIVELES:
            return None, f"nivel inválido en {llave}"
        evaluacion[llave] = nivel

    puntuacion = datos["puntuacion_talento_por_ia"]
    if isinstance(puntuacion, float) and puntuacion.is_integer():
        puntuacion = int(puntuacion)
    if isinstance(puntuacion, bool) or not isinstance(puntuacion, int) or not 0 <= puntuacion <= 100:
        return None, "puntuación fuera de 0-100 o no entera"
    if nivel_de_puntuacion(puntuacion) != evaluacion["potencial_crecimiento_nivel"]:
        return None, "puntuación fuera del rango del nivel de potencial"
    evaluacion["puntuacion_talento_por_ia"] = puntuacion

    reporte = datos["reporte_ia"].strip() if isinstance(datos["reporte_ia"], str) else ""
    if len(reporte) >= MAX_REPORTE:
        reporte = recortar_reporte(reporte)
    if not reporte or len(reporte) > MAX_REPORTE:
        return None, f"reporte vacío o de más de {MAX_REPORTE} caracteres"
    evaluacion["reporte_ia"] = reporte
    return evaluacion, None


def pedir_evaluacion(prompt, segundos):
    # Una llamada al modelo. Deja pasar ConnectionError, ollama.ResponseError y
    # httpx.TimeoutException para que evaluaciones.py los traduzca a E-101/E-102.
    respuesta = obtener_cliente(timeout=segundos).generate(
        model=config.OLLAMA_MODEL, prompt=prompt, format=ESQUEMA,
        options={"temperature": 0.2}, keep_alive=MANTENER_CARGADO,
    )
    return respuesta.response


# --- Precarga del modelo: la primera respuesta (carga en memoria) tardó 120 s > 90 s ---

_precargando = threading.Lock()
_ultima_precarga = 0.0
PRECARGA_CADA_SEG = 300


def _cargar_modelo():
    # Un prompt vacío solo sube el modelo a memoria (o renueva MANTENER_CARGADO).
    # Va sin tiempo límite: si el cliente se desconecta antes, Ollama cancela la carga.
    obtener_cliente().generate(model=config.OLLAMA_MODEL, prompt="", keep_alive=MANTENER_CARGADO)


def precargar():
    # Carga el modelo en segundo plano al iniciar sesión; no bloquea la pantalla
    global _ultima_precarga
    if time.time() - _ultima_precarga < PRECARGA_CADA_SEG or not _precargando.acquire(blocking=False):
        return
    _ultima_precarga = time.time()

    def cargar():
        try:
            _cargar_modelo()
        except Exception as error:
            errores.registrar_aviso("E-101", f"precarga del modelo: {error}")
        finally:
            _precargando.release()

    threading.Thread(target=cargar, daemon=True).start()


def asegurar_carga():
    # Antes de evaluar: espera a la precarga en curso o carga el modelo si no está en
    # memoria, para que la carga no consuma el tiempo máximo ni un intento.
    # Deja pasar ConnectionError y ollama.ResponseError (E-101).
    with _precargando:
        if not any(modelo.model == config.OLLAMA_MODEL for modelo in obtener_cliente().ps().models):
            _cargar_modelo()
