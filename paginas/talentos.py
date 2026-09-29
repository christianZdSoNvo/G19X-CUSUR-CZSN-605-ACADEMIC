from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "ver_talentos")

en_construccion("Talentos", fase=2)
