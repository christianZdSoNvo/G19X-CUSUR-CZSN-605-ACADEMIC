from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "paneles")

en_construccion("Paneles analíticos", fase=4)
