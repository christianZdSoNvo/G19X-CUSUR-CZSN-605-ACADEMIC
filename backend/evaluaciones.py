import httpx
import ollama

from backend import alertas, bitacora, db, errores, ia, permisos

# Evaluación con IA (PRD, 6.8, 9.10, 9.11 y 10). Cada llamada al modelo cuenta como
# un intento, aunque falle o se pase del tiempo. Los intentos se cuentan en la
# bitácora (acción "evaluacion_ia") porque las evaluaciones fallidas no se guardan
# en Evaluaciones; se renuevan cada día o al modificarse el registro del talento.

SIN_CLASIFICAR = "Sin clasificar"
# Matriz 9-box (PRD, 9.11): (potencial, desempeño) -> clasificación
MATRIZ_9BOX = {
    ("alto", "bajo"): "Diamante en bruto",
    ("alto", "medio"): "Futuro líder",
    ("alto", "alto"): "Alta estrella",
    ("medio", "bajo"): "Necesita desarrollo",
    ("medio", "medio"): "Colaborador sólido",
    ("medio", "alto"): "Profesional clave",
    ("bajo", "bajo"): "Necesita mejora",
    ("bajo", "medio"): "Colaborador efectivo",
    ("bajo", "alto"): "Especialista confiable",
}
COLUMNAS = (*ia.LLAVES, "clasificacion_9box")


def clasificar_9box(desempeno_previo, potencial):
    if desempeno_previo is None:
        return SIN_CLASIFICAR
    return MATRIZ_9BOX[(potencial, ia.nivel_de_puntuacion(desempeno_previo))]


def _parametros(cursor):
    cursor.execute(
        "SELECT clave, valor FROM Configuracion_sistema WHERE clave IN "
        "('tiempo_max_ia_seg', 'intentos_ia_por_dia')"
    )
    return {fila["clave"]: int(fila["valor"]) for fila in cursor.fetchall()}


def _intentos_usados(cursor, id_talento):
    # Intentos de hoy posteriores a la última alta o edición del talento. Se compara
    # por id_bitacora (no por hora) para que una edición en el mismo segundo sí cuente.
    # El cambio de foto no cuenta como edición: la foto no se envía al modelo.
    cursor.execute(
        "SELECT COALESCE(MAX(id_bitacora), 0) AS desde FROM Bitacora "
        "WHERE tabla_afectada = 'Talentos' AND id_registro_afectado = %s AND accion IN ('alta', 'edicion') "
        "AND JSON_EXTRACT(detalle, '$.foto') IS NULL",
        (id_talento,),
    )
    desde = cursor.fetchone()["desde"]
    cursor.execute(
        "SELECT COALESCE(SUM(JSON_EXTRACT(detalle, '$.intentos')), 0) AS usados FROM Bitacora "
        "WHERE tabla_afectada = 'Talentos' AND id_registro_afectado = %s AND accion = 'evaluacion_ia' "
        "AND id_bitacora > %s AND fecha_hora >= CURDATE()",
        (id_talento, desde),
    )
    return int(cursor.fetchone()["usados"])


def estado(id_talento):
    # Intentos usados, límite diario y tiempo máximo por intento, para la pantalla
    with db.transaccion() as cursor:
        parametros = _parametros(cursor)
        return {"usados": _intentos_usados(cursor, id_talento),
                "limite": parametros["intentos_ia_por_dia"],
                "segundos": parametros["tiempo_max_ia_seg"]}


def ultima(usuario, id_talento):
    # Última evaluación del talento (o None); el Encargado solo las de su área
    with db.transaccion() as cursor:
        cursor.execute("SELECT area FROM Talentos WHERE id_talento = %s", (id_talento,))
        talento = cursor.fetchone()
        if talento is None:
            return None
        permisos.exigir_area(usuario, talento["area"])
        cursor.execute(
            "SELECT id_evaluacion, fecha_evaluacion, " + ", ".join(COLUMNAS) + " FROM Evaluaciones "
            "WHERE id_talento = %s ORDER BY id_evaluacion DESC LIMIT 1",
            (id_talento,),
        )
        return cursor.fetchone()


def evaluar(administrador, id_talento):
    # Pide la evaluación al modelo, la valida y la guarda con su clasificación 9-box.
    # Devuelve la evaluación guardada; si falla lanza ErrorSistema (E-101 a E-104).
    permisos.exigir(administrador, "evaluar_ia")
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT id_talento, nombre, area, desempeno_previo, competencias, capacitacion, experiencia, "
            "objetivos_futuros, liderazgo_previo FROM Talentos WHERE id_talento = %s AND activo",
            (id_talento,),
        )
        talento = cursor.fetchone()
        parametros = _parametros(cursor)
        disponibles = parametros["intentos_ia_por_dia"] - _intentos_usados(cursor, id_talento)
    if talento is None:
        raise errores.ErrorSistema("E-003")
    if disponibles <= 0:
        raise errores.ErrorSistema("E-104")

    usados, rechazos, evaluacion, codigo = 0, [], None, None
    try:
        ia.asegurar_carga()
    except (ConnectionError, ollama.ResponseError) as error:
        errores.registrar("E-101", error)
        raise errores.ErrorSistema("E-101") from error
    while usados < disponibles:
        prompt = ia.construir_prompt(talento, reintento=bool(rechazos))
        try:
            respuesta = ia.pedir_evaluacion(prompt, parametros["tiempo_max_ia_seg"])
        except (ConnectionError, ollama.ResponseError) as error:
            # Sin conexión o modelo no descargado: no se gasta el intento
            errores.registrar("E-101", error)
            codigo = "E-101"
            break
        except httpx.TimeoutException as error:
            usados += 1
            errores.registrar("E-102", error)
            codigo = "E-102"
            break
        usados += 1
        evaluacion, motivo = ia.validar_respuesta(respuesta)
        if evaluacion is not None:
            break
        rechazos.append(motivo)
        errores.registrar_aviso("E-103", {"id_talento": id_talento, "intento": usados, "motivo": motivo,
                                          "respuesta": (respuesta or "")[:300]})
    else:
        codigo = "E-103"

    if evaluacion is None:
        if usados:
            with db.transaccion() as cursor:
                bitacora.registrar(cursor, administrador["id_usuario"], "evaluacion_ia", "Talentos", id_talento,
                                   {"resultado": codigo, "intentos": usados, "rechazos": rechazos})
        raise errores.ErrorSistema(codigo)

    evaluacion["clasificacion_9box"] = clasificar_9box(talento["desempeno_previo"],
                                                       evaluacion["potencial_crecimiento_nivel"])
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT potencial_crecimiento_nivel, puntuacion_talento_por_ia FROM Evaluaciones WHERE id_talento = %s "
            "ORDER BY id_evaluacion DESC LIMIT 1",
            (id_talento,),
        )
        anterior = cursor.fetchone()
        cursor.execute(
            "INSERT INTO Evaluaciones (id_talento, fecha_evaluacion, " + ", ".join(COLUMNAS) + ") "
            "VALUES (%s, CURDATE(), " + ", ".join(["%s"] * len(COLUMNAS)) + ")",
            (id_talento, *(evaluacion[columna] for columna in COLUMNAS)),
        )
        evaluacion["id_evaluacion"] = cursor.lastrowid
        # Eventos automáticos de la línea de tiempo (PRD, 9.10)
        nivel = evaluacion["potencial_crecimiento_nivel"]
        _evento(cursor, administrador, id_talento, "evaluacion_ia",
                f"Evaluación con IA: potencial {nivel}, {evaluacion['puntuacion_talento_por_ia']} puntos, "
                f"{evaluacion['clasificacion_9box']}.")
        if anterior is not None and anterior["potencial_crecimiento_nivel"] != nivel:
            _evento(cursor, administrador, id_talento, "cambio_clasificacion",
                    f"Potencial de crecimiento: {anterior['potencial_crecimiento_nivel']} -> {nivel}.")
        # Alertas de variación (PRD, 6.6)
        alertas.al_evaluar(cursor, talento, anterior, evaluacion)
        bitacora.registrar(cursor, administrador["id_usuario"], "evaluacion_ia", "Talentos", id_talento,
                           {"resultado": "valida", "intentos": usados, "rechazos": rechazos,
                            "id_evaluacion": evaluacion["id_evaluacion"]})
    return evaluacion


def _evento(cursor, administrador, id_talento, tipo, descripcion):
    cursor.execute(
        "INSERT INTO Eventos_talento (id_talento, tipo_evento, descripcion, fecha_evento, "
        "id_usuario_registro) VALUES (%s, %s, %s, CURDATE(), %s)",
        (id_talento, tipo, descripcion, administrador["id_usuario"]),
    )
