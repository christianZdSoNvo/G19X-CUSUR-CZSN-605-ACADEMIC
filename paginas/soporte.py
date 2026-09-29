from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "soporte")

en_construccion("Soporte", fase=7)
