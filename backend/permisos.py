from backend import errores

ADMINISTRADOR = "Administrador RH"
ENCARGADO = "Encargado de area"
# Como se muestran en pantalla (en la BD el ENUM va sin acentos)
NOMBRES_CARGO = {ADMINISTRADOR: "Administrador de RH", ENCARGADO: "Encargado de área"}
_AMBOS = frozenset({ADMINISTRADOR, ENCARGADO})
_SOLO_ADMINISTRADOR = frozenset({ADMINISTRADOR})

# Matriz de permisos por rol (PRD, 6.7): función -> cargos que la pueden usar.
# El alcance por área se revisa aparte con area_permitida() y exigir_area().
MATRIZ = {
    "ver_talentos": _AMBOS,
    "editar_talentos": _SOLO_ADMINISTRADOR,
    "evaluar_ia": _SOLO_ADMINISTRADOR,
    "paneles": _AMBOS,
    "reportes": _AMBOS,
    "historial": _AMBOS,
    "alertas": _AMBOS,
    "notificaciones": _AMBOS,
    "gestion_usuarios": _SOLO_ADMINISTRADOR,
    "parametros": _SOLO_ADMINISTRADOR,
    "consultar_manuales": _AMBOS,
    "editar_manuales": _SOLO_ADMINISTRADOR,
    "soporte": _AMBOS,
    "bitacora": _SOLO_ADMINISTRADOR,
    "configuracion_general": _AMBOS,
}


def es_administrador(usuario):
    return usuario["cargo"] == ADMINISTRADOR


def puede(usuario, funcion):
    return usuario["cargo"] in MATRIZ[funcion]


def exigir(usuario, funcion):
    if not puede(usuario, funcion):
        _denegar(usuario, {"funcion": funcion})


def area_permitida(usuario):
    # None = todas las áreas (Administrador); el Encargado solo ve la suya
    return None if es_administrador(usuario) else usuario["area"]


def exigir_area(usuario, area):
    if not es_administrador(usuario) and area != usuario["area"]:
        _denegar(usuario, {"area_solicitada": area})


def _denegar(usuario, detalle):
    errores.registrar_aviso("E-304", {"id_usuario": usuario["id_usuario"], **detalle})
    raise errores.ErrorSistema("E-304")
