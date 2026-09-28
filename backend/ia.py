"""Conexión con Ollama (modelo de IA local)."""

import ollama

from backend import config


def obtener_cliente():
    """Crea un cliente de Ollama con la dirección del archivo .env."""
    return ollama.Client(host=config.OLLAMA_HOST)


def probar_conexion():
    """Comprueba que Ollama responde y si el modelo configurado está descargado.

    Devuelve (modelos_instalados, modelo_disponible).
    """
    respuesta = obtener_cliente().list()
    modelos = [m.model for m in respuesta.models]
    return modelos, config.OLLAMA_MODEL in modelos
