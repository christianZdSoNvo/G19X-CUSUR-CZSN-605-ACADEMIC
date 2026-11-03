import logging
from pathlib import Path

# Catálogo de códigos de error (PRD, sección 7)
CATALOGO = {
    "E-001": "No fue posible conectar con la base de datos. Reinicie el sistema o contacte a soporte.",
    "E-002": "Error de configuración del sistema. Contacte a soporte.",
    "E-003": "No se pudo guardar la información. Revise los campos marcados.",
    "E-004": "Ya existe un registro con ese correo o usuario.",
    "E-101": "El modelo de IA no está disponible. Intente de nuevo; si el problema sigue, contacte a soporte.",
    "E-102": "La evaluación tardó demasiado. Intente de nuevo.",
    "E-103": "La IA no devolvió una evaluación válida. Intente más tarde.",
    "E-104": "Se alcanzó el límite de evaluaciones para este talento.",
    "E-201": "No se pudo generar el PDF; se generó un archivo de texto con los datos.",
    "E-202": "No se pudo generar el Excel; se generó un archivo de texto con los datos.",
    "E-301": "Usuario o contraseña incorrectos.",
    "E-302": "Cuenta bloqueada temporalmente. Intente en {tiempo}.",
    "E-303": "Su sesión expiró. Inicie sesión de nuevo.",
    "E-304": "No tiene permisos para acceder a esta sección.",
    "E-401": "No hay manuales disponibles. Contacte a soporte: {correo_soporte}.",
    "E-402": "La imagen debe ser PNG o JPG de máximo 5 MB.",
}
# E-101 cuando Ollama no responde o cuando responde pero el modelo del .env no está descargado
OLLAMA_NO_RESPONDE = ("Ollama no responde. Inícielo desde el ícono junto al reloj o, si no aparece ahí, "
                      "búsquelo como «Ollama» en el menú Inicio y ábralo; luego intente de nuevo.")
MODELO_NO_DESCARGADO = "El modelo de IA {modelo} no está descargado. Ejecute: ollama pull {modelo}"

RUTA_LOG = Path(__file__).resolve().parent.parent / "logs" / "sistema.log"

_log = logging.getLogger("sistema")


class ErrorSistema(Exception):
    # "datos" llena los huecos del mensaje (p. ej. tiempo en E-302); "texto" cambia
    # el mensaje del catálogo por otro del mismo código (OLLAMA_NO_RESPONDE, MODELO_NO_DESCARGADO)
    def __init__(self, codigo, texto=None, **datos):
        self.codigo = codigo
        self.texto = texto
        self.datos = datos
        super().__init__(f"{codigo}: {self.mensaje}")

    @property
    def mensaje(self):
        texto = self.texto or CATALOGO[self.codigo]
        return texto.format(**self.datos) if self.datos else texto


def _preparar_log():
    # Streamlit vuelve a ejecutar los módulos; el manejador se agrega una sola vez
    if not _log.handlers:
        manejador = logging.FileHandler(RUTA_LOG, encoding="utf-8")
        manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _log.addHandler(manejador)
        _log.setLevel(logging.INFO)
        _log.propagate = False


def registrar(codigo, error):
    _preparar_log()
    _log.error(codigo, exc_info=error)


def registrar_aviso(codigo, detalle):
    # Para situaciones esperadas (p. ej. E-304) que no traen una excepción
    _preparar_log()
    _log.warning("%s %s", codigo, detalle)
