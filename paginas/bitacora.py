from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "bitacora")

en_construccion("Bitácora", fase=7)
