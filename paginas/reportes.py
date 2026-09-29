from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "reportes")

en_construccion("Reportes", fase=5)
