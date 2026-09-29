from backend import permisos, sesion
from backend.interfaz import en_construccion

permisos.exigir(sesion.usuario_actual(), "historial")

en_construccion("Historial y evolución", fase=4)
