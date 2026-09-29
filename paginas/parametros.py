from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "parametros")

en_construccion("Parámetros del sistema", fase=7)
