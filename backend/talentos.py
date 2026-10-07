import datetime
import re

from backend import alertas, bitacora, catalogos, db, errores, fotos, permisos

# Gestión de talentos (PRD, 6.1, 6.4 y 13.8). Las funciones de consulta reciben al
# usuario de la sesión para limitar al Encargado a su área; las de escritura son
# solo del Administrador de RH y lo dejan como autor en la bitácora.

SIN_REGISTRO = "Sin registro"
NO_IDENTIFICADO = "Talento no identificado, favor de intentar de nuevo"
DUPLICADO = errores.CATALOGO["E-004"]
GENERALES = ("nombre", "area", "correo", "tel_mx", "fecha_ingreso")
# Indicadores de texto -> tamaño del campo en la BD (PRD, 9.1)
INDICADORES = {
    "competencias": 200,
    "capacitacion": 400,
    "experiencia": 300,
    "objetivos_futuros": 200,
    "liderazgo_previo": 300,
}
CAMPOS = (*GENERALES, "desempeno_previo", *INDICADORES)
MAX_MOTIVO = 200


class TalentoDeBaja(Exception):
    # El correo pertenece a un talento dado de baja: se ofrece reactivarlo (PRD, 9.1)
    def __init__(self, id_talento, nombre):
        super().__init__(f"El correo pertenece al talento {id_talento}, dado de baja.")
        self.id_talento = id_talento
        self.nombre = nombre


def limpiar(datos):
    limpio = {campo: str(datos.get(campo) or "").strip() for campo in GENERALES if campo != "fecha_ingreso"}
    limpio["correo"] = limpio["correo"].lower()
    limpio["fecha_ingreso"] = datos.get("fecha_ingreso")
    limpio["desempeno_previo"] = datos.get("desempeno_previo")
    if isinstance(limpio["desempeno_previo"], float) and limpio["desempeno_previo"].is_integer():
        limpio["desempeno_previo"] = int(limpio["desempeno_previo"])
    for campo in INDICADORES:
        # Vacío equivale al valor por omisión de la BD
        limpio[campo] = str(datos.get(campo) or "").strip() or SIN_REGISTRO
    return limpio


def validar(datos):
    # Devuelve {campo: mensaje} para mostrar cada error debajo de su campo (PRD, 13.8)
    problemas = {}
    if not datos["nombre"] or len(datos["nombre"]) > 50:
        problemas["nombre"] = "El nombre es obligatorio y admite hasta 50 caracteres."
    if datos["area"] not in catalogos.AREAS:
        problemas["area"] = "Seleccione un área válida."
    if len(datos["correo"]) > 70 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", datos["correo"]):
        problemas["correo"] = "Escriba un correo válido de hasta 70 caracteres."
    if not re.fullmatch(r"[0-9]{10}", datos["tel_mx"]):
        problemas["tel_mx"] = "El teléfono debe tener 10 dígitos."
    fecha = datos["fecha_ingreso"]
    if not isinstance(fecha, datetime.date):
        problemas["fecha_ingreso"] = "La fecha de ingreso es obligatoria."
    elif fecha > datetime.date.today():
        problemas["fecha_ingreso"] = "La fecha de ingreso no puede ser posterior a hoy."
    desempeno = datos["desempeno_previo"]
    if desempeno is not None and (not isinstance(desempeno, int) or not 0 <= desempeno <= 100):
        problemas["desempeno_previo"] = "El desempeño previo debe ser un número entero de 0 a 100."
    for campo, maximo in INDICADORES.items():
        if len(datos[campo]) > maximo:
            problemas[campo] = f"Admite hasta {maximo} caracteres."
    return problemas


def buscar(usuario, texto="", area=None):
    # Buscador por ID o nombre y lista filtrable (PRD, 6.4); solo talentos activos.
    # El Encargado siempre queda limitado a su área, aunque pida otra.
    condiciones, parametros = ["activo"], []
    area = permisos.area_permitida(usuario) or area
    if area:
        condiciones.append("area = %s")
        parametros.append(area)
    texto = texto.strip()
    if texto.isdigit():
        condiciones.append("id_talento = %s")
        parametros.append(int(texto))
    elif texto:
        condiciones.append("nombre LIKE %s")
        parametros.append(f"%{texto}%")
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_talento, " + ", ".join(CAMPOS) + ", fecha_modificacion FROM Talentos "
            "WHERE " + " AND ".join(condiciones) + " ORDER BY nombre",
            tuple(parametros),
        )
        return cursor.fetchall()


def obtener(usuario, id_talento):
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_talento, " + ", ".join(CAMPOS) + ", activo, fecha_modificacion, foto "
            "FROM Talentos WHERE id_talento = %s",
            (id_talento,),
        )
        talento = cursor.fetchone()
    if talento is not None:
        permisos.exigir_area(usuario, talento["area"])
    return talento


def listar_bajas(administrador):
    permisos.exigir(administrador, "editar_talentos")
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_talento, nombre, area, correo, fecha_baja, motivo_baja "
            "FROM Talentos WHERE NOT activo ORDER BY fecha_baja DESC, nombre"
        )
        return cursor.fetchall()


def crear(administrador, datos):
    # Devuelve (problemas, id del talento nuevo). Si el correo ya es de un talento
    # activo se marca E-004 en el campo; si es de uno dado de baja, lanza TalentoDeBaja.
    permisos.exigir(administrador, "editar_talentos")
    datos = limpiar(datos)
    problemas = validar(datos)
    if problemas:
        return problemas, None

    with db.transaccion() as cursor:
        existente = _por_correo(cursor, datos["correo"])
        if existente is not None:
            if not existente["activo"]:
                raise TalentoDeBaja(existente["id_talento"], existente["nombre"])
            return {"correo": DUPLICADO}, None
        cursor.execute(
            "INSERT INTO Talentos (" + ", ".join(CAMPOS) + ", fecha_modificacion) "
            "VALUES (" + ", ".join(["%s"] * len(CAMPOS)) + ", CURDATE())",
            tuple(datos[campo] for campo in CAMPOS),
        )
        id_nuevo = cursor.lastrowid
        _evento(cursor, administrador, id_nuevo, "ingreso",
                f"Ingreso al área {datos['area']}.", datos["fecha_ingreso"])
        bitacora.registrar(cursor, administrador["id_usuario"], "alta", "Talentos", id_nuevo,
                           {"nuevo": datos})
    return {}, id_nuevo


def editar(administrador, id_talento, datos):
    permisos.exigir(administrador, "editar_talentos")
    datos = limpiar(datos)
    problemas = validar(datos)
    if problemas:
        return problemas

    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT " + ", ".join(CAMPOS) + ", activo FROM Talentos WHERE id_talento = %s FOR UPDATE",
            (id_talento,),
        )
        actual = cursor.fetchone()
        if actual is None or not actual["activo"]:
            return {"nombre": "El talento no existe o fue dado de baja."}
        cambios = {campo: datos[campo] for campo in CAMPOS if datos[campo] != actual[campo]}
        if not cambios:
            return {}
        if "correo" in cambios and _por_correo(cursor, datos["correo"]) is not None:
            return {"correo": DUPLICADO}

        cursor.execute(
            "UPDATE Talentos SET " + ", ".join(f"{campo} = %s" for campo in cambios)
            + ", fecha_modificacion = CURDATE() WHERE id_talento = %s",
            (*cambios.values(), id_talento),
        )
        # Eventos automáticos de la línea de tiempo (PRD, 9.10)
        hoy = datetime.date.today()
        if "desempeno_previo" in cambios:
            _evento(cursor, administrador, id_talento, "cambio_desempeno",
                    f"Desempeño previo: {_texto(actual['desempeno_previo'])} -> "
                    f"{_texto(datos['desempeno_previo'])}.", hoy)
        if "area" in cambios:
            _evento(cursor, administrador, id_talento, "cambio_area",
                    f"Cambio de área: {actual['area']} -> {datos['area']}.", hoy)
        if "desempeno_previo" in cambios:
            # Alertas de variación del desempeño (PRD, 6.6), con el nombre y el área ya actualizados
            alertas.al_editar(cursor, {"id_talento": id_talento, "nombre": datos["nombre"], "area": datos["area"]},
                              actual["desempeno_previo"], datos["desempeno_previo"])
        bitacora.registrar(cursor, administrador["id_usuario"], "edicion", "Talentos", id_talento,
                           {"anterior": {campo: actual[campo] for campo in cambios}, "nuevo": cambios})
    return {}


def dar_de_baja(administrador, id_talento, motivo):
    # Baja lógica (PRD, 6.1): se conservan sus evaluaciones y eventos
    permisos.exigir(administrador, "editar_talentos")
    motivo = motivo.strip()
    if not motivo or len(motivo) > MAX_MOTIVO:
        return {"motivo": f"El motivo es obligatorio y admite hasta {MAX_MOTIVO} caracteres."}
    with db.transaccion() as cursor:
        cursor.execute(
            "UPDATE Talentos SET activo = FALSE, fecha_baja = CURDATE(), motivo_baja = %s, "
            "fecha_modificacion = CURDATE() WHERE id_talento = %s AND activo",
            (motivo, id_talento),
        )
        if cursor.rowcount:
            bitacora.registrar(cursor, administrador["id_usuario"], "baja", "Talentos", id_talento,
                               {"motivo_baja": motivo})
    return {}


def reactivar(administrador, id_talento):
    permisos.exigir(administrador, "editar_talentos")
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT fecha_baja, motivo_baja FROM Talentos WHERE id_talento = %s AND NOT activo FOR UPDATE",
            (id_talento,),
        )
        baja = cursor.fetchone()
        if baja is None:
            return
        cursor.execute(
            "UPDATE Talentos SET activo = TRUE, fecha_baja = NULL, motivo_baja = NULL, "
            "fecha_modificacion = CURDATE() WHERE id_talento = %s",
            (id_talento,),
        )
        bitacora.registrar(cursor, administrador["id_usuario"], "edicion", "Talentos", id_talento,
                           {"activo": True, "baja_anterior": baja})


def cambiar_foto(administrador, id_talento, contenido):
    # Guarda (contenido = bytes de la imagen) o quita (None) la foto de perfil; E-402 si
    # la imagen no es válida. No renueva los intentos de IA: la foto no se envía al modelo.
    permisos.exigir(administrador, "editar_talentos")
    foto = fotos.preparar(contenido) if contenido else None
    with db.transaccion() as cursor:
        cursor.execute("SELECT id_talento FROM Talentos WHERE id_talento = %s AND activo FOR UPDATE", (id_talento,))
        if cursor.fetchone() is None:
            return
        cursor.execute("UPDATE Talentos SET foto = %s WHERE id_talento = %s", (foto, id_talento))
        bitacora.registrar(cursor, administrador["id_usuario"], "edicion", "Talentos", id_talento,
                           {"foto": "actualizada" if foto else "eliminada"})


def _por_correo(cursor, correo):
    cursor.execute("SELECT id_talento, nombre, activo FROM Talentos WHERE correo = %s", (correo,))
    return cursor.fetchone()


def _evento(cursor, administrador, id_talento, tipo, descripcion, fecha):
    cursor.execute(
        "INSERT INTO Eventos_talento (id_talento, tipo_evento, descripcion, fecha_evento, "
        "id_usuario_registro) VALUES (%s, %s, %s, %s, %s)",
        (id_talento, tipo, descripcion, fecha, administrador["id_usuario"]),
    )


def _texto(desempeno):
    return SIN_REGISTRO if desempeno is None else str(desempeno)
