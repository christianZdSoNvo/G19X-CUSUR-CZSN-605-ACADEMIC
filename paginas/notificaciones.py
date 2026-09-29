from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "notificaciones")

en_construccion("Notificaciones y alertas", fase=6)
