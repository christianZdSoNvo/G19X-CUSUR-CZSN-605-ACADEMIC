from backend import permisos, sesion
from backend.interfaz import en_construccion

# Ambos roles consultan; solo el Administrador edita ("editar_manuales"). El Encargado
# solo verá los manuales de las secciones que tiene en su menú.
permisos.exigir(sesion.usuario_actual(), "consultar_manuales")

en_construccion("Manuales", fase=7)
