import datetime
import io
import re
import unicodedata

import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from backend import analitica, bitacora, db, errores, evaluaciones, interfaz, permisos, talentos

# Reportes individuales y generales en PDF y Excel (PRD, 6.4, 13.2 y 14). Si falla la
# generación del archivo se entrega un archivo de texto con los mismos datos (E-201 y
# E-202). Toda exportación, exitosa o no, queda en la bitácora.

AZUL = (11, 31, 58)
DORADO = (201, 162, 39)
ROJO = (178, 34, 52)
GRIS_CLARO = (242, 243, 245)
GRIS_LINEA = (200, 203, 208)
GRIS_TEXTO = (95, 99, 104)
BLANCO = (255, 255, 255)
COLOR_NIVEL = {"alto": AZUL, "medio": DORADO, "bajo": ROJO}
LEYENDA = "Documento confidencial – uso interno"
SIN_EVALUACION = "Sin evaluación"

FORMATOS = {
    "pdf": {"extension": ".pdf", "mime": "application/pdf", "error": "E-201"},
    "excel": {"extension": ".xlsx", "error": "E-202",
              "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}
MIME_TEXTO = "text/plain"

NOMBRES_CAMPOS = {
    "id_talento": "ID",
    "nombre": "Nombre",
    "area": "Área",
    "correo": "Correo",
    "tel_mx": "Teléfono",
    "fecha_ingreso": "Fecha de ingreso",
    "desempeno_previo": "Desempeño previo",
    "competencias": "Competencias",
    "capacitacion": "Capacitación",
    "experiencia": "Experiencia",
    "objetivos_futuros": "Objetivos futuros",
    "liderazgo_previo": "Liderazgo previo",
    "fecha_modificacion": "Última modificación",
}
_COLUMNAS_TALENTO = tuple(NOMBRES_CAMPOS)
# Lado de la foto de perfil en el PDF individual (mm)
LADO_FOTO = 32
_COLUMNAS_EVALUACION = ("id_evaluacion", "fecha_evaluacion", *evaluaciones.COLUMNAS)


# --- Formato de valores ---

def fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor is not None and not pd.isna(valor) else ""


def nivel(valor):
    return valor.capitalize() if isinstance(valor, str) else ""


def _desempeno(valor):
    return talentos.SIN_REGISTRO if valor is None or pd.isna(valor) else str(int(valor))


def _para_archivo(texto):
    # Solo letras, números, guion y guion bajo (sin acentos) para el nombre del archivo
    simple = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", simple).strip("_") or "sin_nombre"


def nombre_archivo(datos, extension, generado):
    dia = generado.strftime("%Y%m%d")
    if datos["tipo"] == "individual":
        talento = datos["talento"]
        base = f"Reporte_{talento['id_talento']}_{_para_archivo(talento['nombre'])}_{dia}"
    else:
        base = f"Reporte_general_{_para_archivo(datos['filtros']['area'] or 'todas')}_{dia}"
    return base + extension


# --- Datos ---

def datos_individual(usuario, id_talento, id_evaluacion=None):
    # Talento con todas sus evaluaciones y eventos; el Encargado solo los de su área.
    # "evaluacion" es la que se detalla en el PDF: la elegida o, si no se elige, la última.
    permisos.exigir(usuario, "reportes")
    talento = talentos.obtener(usuario, id_talento)
    if talento is None:
        return None
    with db.transaccion() as cursor:
        cursor.execute(
            "SELECT " + ", ".join(_COLUMNAS_EVALUACION) + " FROM Evaluaciones "
            "WHERE id_talento = %s ORDER BY id_evaluacion",
            (id_talento,),
        )
        lista = cursor.fetchall()
    eventos = analitica.historial(usuario, id_talento)["eventos"]
    ultima = lista[-1] if lista else None
    elegida = next((e for e in lista if e["id_evaluacion"] == id_evaluacion), None)
    return {"tipo": "individual", "talento": talento, "evaluaciones": lista, "eventos": eventos,
            "ultima": ultima, "evaluacion": elegida or ultima}


def _evaluacion_detallada(datos):
    # Evaluación que va en "Resultado" y, si no es la última, la fecha de la más reciente
    evaluacion, ultima = datos.get("evaluacion") or datos["ultima"], datos["ultima"]
    anterior = evaluacion is not None and evaluacion["id_evaluacion"] != ultima["id_evaluacion"]
    nota = (f"Evaluación anterior elegida para este reporte; la más reciente es del "
            f"{fecha(ultima['fecha_evaluacion'])}." if anterior else None)
    return evaluacion, nota


def datos_general(usuario, area=None, niveles=(), clasificaciones=(), fechas=None, hoy=None):
    # Resumen del grupo filtrado con los mismos filtros de los paneles (PRD, 13.1)
    permisos.exigir(usuario, "reportes")
    hoy = hoy or datetime.date.today()
    area = permisos.area_permitida(usuario) or area
    base = analitica.talentos_con_ultima_evaluacion(usuario)
    todas = analitica.todas_las_evaluaciones(usuario)
    filtrado = analitica.filtrar(base, area=area, niveles=niveles, clasificaciones=clasificaciones,
                                 fechas=fechas) if not base.empty else base
    ids = [int(valor) for valor in filtrado["id_talento"]]
    registros = {}
    if ids:
        with db.transaccion() as cursor:
            cursor.execute(
                "SELECT " + ", ".join(_COLUMNAS_TALENTO) + " FROM Talentos WHERE id_talento IN ("
                + ", ".join(["%s"] * len(ids)) + ")",
                tuple(ids),
            )
            registros = {fila["id_talento"]: fila for fila in cursor.fetchall()}
    filtros = {"area": area, "niveles": list(niveles), "clasificaciones": list(clasificaciones),
               "fechas": tuple(fechas) if fechas else None}
    return {"tipo": "general", "filtros": filtros, **resumen_general(filtrado, todas, fechas, hoy),
            "talentos": [{**registros[int(fila["id_talento"])], **_ultima_de(fila)}
                         for _, fila in filtrado.iterrows()]}


def _ultima_de(fila):
    if pd.isna(fila["id_evaluacion"]):
        return {"puntuacion_talento_por_ia": None, "potencial_crecimiento_nivel": None,
                "clasificacion_9box": None, "fecha_evaluacion": None}
    return {"puntuacion_talento_por_ia": int(fila["puntuacion_talento_por_ia"]),
            "potencial_crecimiento_nivel": fila["potencial_crecimiento_nivel"],
            "clasificacion_9box": fila["clasificacion_9box"], "fecha_evaluacion": fila["fecha_evaluacion"]}


def resumen_general(filtrado, todas, fechas, hoy):
    # Indicadores, distribución, promedios, 9-box y top 10 (cálculo puro, sin BD).
    # Sin filtro de fechas, el periodo de las evaluaciones es el mes en curso.
    evaluados = analitica.evaluados(filtrado)
    conteo = evaluados["potencial_crecimiento_nivel"].value_counts()
    porcentajes = {nivel_: (round(100 * int(conteo.get(nivel_, 0)) / len(evaluados), 1) if len(evaluados) else None)
                   for nivel_ in analitica.NIVELES}
    periodo = tuple(fechas) if fechas else (hoy.replace(day=1), hoy)
    grupo = todas[todas["id_talento"].isin(filtrado["id_talento"])]
    en_periodo = grupo["fecha_evaluacion"].map(lambda f: periodo[0] <= f <= periodo[1]) if not grupo.empty else []
    distribucion = analitica.distribucion_por_area(filtrado) if not evaluados.empty else pd.DataFrame()
    promedios = analitica.promedio_por_area(filtrado)
    top = evaluados.sort_values(["puntuacion_talento_por_ia", "nombre"], ascending=[False, True]).head(10)
    return {
        "indicadores": {
            "total": len(filtrado),
            "porcentajes": porcentajes,
            "periodo": periodo,
            "evaluaciones_periodo": int(sum(en_periodo)),
            "sin_evaluar": len(filtrado) - len(evaluados),
        },
        "distribucion": [
            {"area": area_, **{n: int(distribucion.loc[area_, n]) for n in analitica.NIVELES},
             "total": int(distribucion.loc[area_].sum()),
             "promedio": float(promedios[area_]) if area_ in promedios else None}
            for area_ in distribucion.index
        ],
        "conteo_9box": analitica.conteo_9box(filtrado) if not filtrado.empty else
        {clasificacion: 0 for clasificacion in analitica.CLASIFICACIONES},
        "top": [{"id_talento": int(fila["id_talento"]), "nombre": fila["nombre"], "area": fila["area"],
                 "puntuacion": int(fila["puntuacion_talento_por_ia"]), "nivel": fila["potencial_crecimiento_nivel"],
                 "clasificacion": fila["clasificacion_9box"]} for _, fila in top.iterrows()],
    }


def descripcion_filtros(filtros):
    # [(filtro, valor)] para mostrar en los archivos
    fechas = filtros["fechas"]
    return [
        ("Área", filtros["area"] or "Todas"),
        ("Nivel de potencial", ", ".join(nivel(n) for n in filtros["niveles"]) or "Todos"),
        ("Clasificación 9-box", ", ".join(filtros["clasificaciones"]) or "Todas"),
        ("Fechas de evaluación", f"{fecha(fechas[0])} al {fecha(fechas[1])}" if fechas else "Sin filtro"),
    ]


def _lineas_indicadores(indicadores):
    periodo = indicadores["periodo"]
    porcentaje = indicadores["porcentajes"]
    return [
        ("Total de talentos", str(indicadores["total"])),
        *((f"Potencial {n}", "Sin evaluaciones" if porcentaje[n] is None else f"{porcentaje[n]} %")
          for n in reversed(analitica.NIVELES)),
        (f"Evaluaciones del periodo ({fecha(periodo[0])} al {fecha(periodo[1])})",
         str(indicadores["evaluaciones_periodo"])),
        ("Talentos sin evaluación", str(indicadores["sin_evaluar"])),
    ]


# --- PDF (fpdf2) ---

_REEMPLAZOS = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "•": "-",
                             "…": "...", "→": "->", " ": " "})


def latin1(texto):
    # Helvetica solo admite latin-1; lo demás se sustituye o se cambia por "?"
    return str(texto).translate(_REEMPLAZOS).encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    # Carta vertical, márgenes de 2.5 cm, Helvetica 11 pt y títulos de 14 pt (PRD, 14)
    def __init__(self, usuario, generado):
        super().__init__(orientation="portrait", unit="mm", format="letter")
        self.usuario = usuario
        self.generado = generado
        self.set_margins(25, 25, 25)
        self.set_auto_page_break(True, margin=25)
        self.set_title(interfaz.NOMBRE)
        self.set_author(usuario["nombre"])
        self.add_page()

    def normalize_text(self, text):
        return super().normalize_text(latin1(text))

    def header(self):
        self.set_y(12)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*AZUL)
        self.cell(0, 7, interfaz.NOMBRE)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIS_TEXTO)
        self.set_x(self.l_margin)
        self.cell(0, 7, interfaz.SIGNIFICADO, align="R")
        self.set_draw_color(*DORADO)
        self.set_line_width(0.6)
        self.line(self.l_margin, 20, self.w - self.r_margin, 20)
        self.set_y(25)
        self._texto()

    def footer(self):
        self.set_y(-20)
        self.set_draw_color(*GRIS_LINEA)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRIS_TEXTO)
        self.cell(0, 5, f"Generado el {self.generado:%d/%m/%Y %H:%M} por {self.usuario['nombre']}",
                  new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, LEYENDA)
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Página {self.page_no()} de {{nb}}", align="R")

    def _texto(self):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(0, 0, 0)

    def titulo(self, texto):
        # Título principal con la línea dorada debajo
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*AZUL)
        self.cell(0, 9, texto, new_x="LMARGIN", new_y="NEXT")
        self._texto()
        self.ln(1)

    def seccion(self, texto, espacio=30):
        # Título de sección; si no cabe con algo de contenido, pasa a la página siguiente
        if self.get_y() + espacio > self.page_break_trigger:
            self.add_page()
        self.ln(3)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*AZUL)
        self.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT")
        self._texto()
        self.ln(1)

    def tabla(self, encabezados, filas, anchos=None, alineaciones=None, colores=None):
        # colores: {(fila, columna): color del texto} para resaltar niveles
        colores = colores or {}
        # Las gráficas dejan otros colores y grosores; la tabla usa los suyos
        self.set_fill_color(*BLANCO)
        self.set_draw_color(*GRIS_LINEA)
        self.set_line_width(0.2)
        self._texto()
        encabezado = FontFace(emphasis="BOLD", color=BLANCO, fill_color=AZUL)
        with self.table(col_widths=anchos, headings_style=encabezado, line_height=6.5,
                        text_align=alineaciones or "LEFT", borders_layout="HORIZONTAL_LINES",
                        cell_fill_color=GRIS_CLARO, cell_fill_mode="ROWS", first_row_as_headings=True,
                        padding=1.2) as tabla:
            fila_pdf = tabla.row()
            for texto in encabezados:
                fila_pdf.cell(texto)
            for i, fila in enumerate(filas):
                fila_pdf = tabla.row()
                for j, texto in enumerate(fila):
                    color = colores.get((i, j))
                    fila_pdf.cell(str(texto), style=FontFace(emphasis="BOLD", color=color) if color else None)

    def pares(self, filas, ancho=None):
        # Tabla de dos columnas "dato: valor" sin encabezado
        with self.table(col_widths=(35, 65), first_row_as_headings=False, line_height=6.5,
                        borders_layout="NONE", padding=0.8, width=ancho, align="LEFT") as tabla:
            for dato, valor in filas:
                fila = tabla.row()
                fila.cell(dato, style=FontFace(emphasis="BOLD", color=AZUL))
                fila.cell(str(valor))

    def linea_de_tiempo(self, fecha_ingreso, lista, eventos, hoy):
        # Gráfica dibujada con las primitivas de fpdf2 (equivale a la del historial):
        # puntuación de IA en el tiempo y eventos como rombos rojos sobre el eje
        alto_total = 72
        if self.get_y() + alto_total > self.page_break_trigger:
            self.add_page()
        x0, y0 = self.l_margin + 12, self.get_y() + 3
        ancho, alto = self.epw - 14, 52
        inicio = fecha_ingreso - datetime.timedelta(days=15)
        dias = max((hoy + datetime.timedelta(days=15) - inicio).days, 1)

        def x_de(dia):
            return x0 + ancho * (dia - inicio).days / dias

        def y_de(puntos):
            return y0 + alto * (1 - (puntos + 5) / 110)

        self.set_font("Helvetica", "", 7)
        self.set_text_color(*GRIS_TEXTO)
        self.set_line_width(0.15)
        for valor in (0, 25, 50, 75, 100):
            self.set_draw_color(*GRIS_LINEA)
            self.line(x0, y_de(valor), x0 + ancho, y_de(valor))
            self.set_xy(x0 - 10, y_de(valor) - 2)
            self.cell(8, 4, str(valor), align="R")
        self.set_draw_color(*GRIS_TEXTO)
        self.line(x0, y0 + alto, x0 + ancho, y0 + alto)
        for paso in range(6):
            dia = inicio + datetime.timedelta(days=round(dias * paso / 5))
            self.set_xy(x_de(dia) - 10, y0 + alto + 1)
            self.cell(20, 4, dia.strftime("%m/%Y"), align="C")

        puntos = [(x_de(fila["fecha_evaluacion"]), y_de(fila["puntuacion_talento_por_ia"]),
                   fila["potencial_crecimiento_nivel"]) for fila in lista]
        if len(puntos) > 1:
            self.set_draw_color(*AZUL)
            self.set_line_width(0.7)
            self.polyline([(x, y) for x, y, _ in puntos])
        for x, y, nivel_ in puntos:
            self.set_fill_color(*COLOR_NIVEL[nivel_])
            self.set_draw_color(*BLANCO)
            self.set_line_width(0.3)
            self.circle(x, y, 1.4, style="DF")
        self.set_fill_color(*ROJO)
        for evento in eventos:
            x, y = x_de(evento["fecha_evento"]), y_de(0)
            self.polygon([(x, y - 1.6), (x + 1.3, y), (x, y + 1.6), (x - 1.3, y)], style="F")

        # Leyenda
        y = y0 + alto + 7
        self.set_xy(x0, y)
        self.set_draw_color(*AZUL)
        self.set_line_width(0.7)
        self.line(x0, y + 2, x0 + 6, y + 2)
        self.set_xy(x0 + 7, y)
        self.cell(40, 4, "Puntuación de IA (color: nivel de potencial)")
        self.set_fill_color(*ROJO)
        xe = x0 + 75
        self.polygon([(xe, y + 0.4), (xe + 1.3, y + 2), (xe, y + 3.6), (xe - 1.3, y + 2)], style="F")
        self.set_xy(xe + 2.5, y)
        self.cell(20, 4, "Eventos")
        for i, nivel_ in enumerate(reversed(analitica.NIVELES)):
            xn = x0 + 100 + i * 18
            self.set_fill_color(*COLOR_NIVEL[nivel_])
            self.circle(xn, y + 2, 1.4, style="F")
            self.set_xy(xn + 2.5, y)
            self.cell(14, 4, nivel(nivel_))
        self.set_xy(self.l_margin, y + 7)
        self._texto()

    def barras(self, filas, maximo, color=AZUL):
        # Barras horizontales sencillas: [(etiqueta, valor)]
        ancho_etiqueta, ancho_barra = 55, self.epw - 70
        for etiqueta, valor in filas:
            y = self.get_y()
            self.set_font("Helvetica", "", 9)
            self.cell(ancho_etiqueta, 6, etiqueta)
            self.set_fill_color(*color)
            largo = ancho_barra * (valor / maximo) if maximo else 0
            if largo > 0:
                self.rect(self.l_margin + ancho_etiqueta, y + 1.2, largo, 3.6, style="F")
            self.set_xy(self.l_margin + ancho_etiqueta + largo + 1.5, y)
            self.cell(15, 6, f"{valor:g}")
            self.set_xy(self.l_margin, y + 6)
        self._texto()


def pdf_individual(datos, usuario, generado):
    talento = datos["talento"]
    ultima, nota = _evaluacion_detallada(datos)
    pdf = _PDF(usuario, generado)
    pdf.titulo("Reporte individual de talento")
    # Foto de perfil (o el avatar genérico) a la derecha de los datos generales
    arriba = pdf.get_y()
    pdf.image(io.BytesIO(bytes(talento["foto"])) if talento.get("foto") else interfaz.AVATAR,
              x=pdf.w - pdf.r_margin - LADO_FOTO, y=arriba, w=LADO_FOTO, h=LADO_FOTO)
    pdf.pares([("ID", talento["id_talento"]), ("Nombre", talento["nombre"]), ("Área", talento["area"]),
               ("Fecha de ingreso", fecha(talento["fecha_ingreso"])),
               ("Desempeño previo", _desempeno(talento["desempeno_previo"]))],
              ancho=pdf.epw - LADO_FOTO - 5)
    pdf.set_y(max(pdf.get_y(), arriba + LADO_FOTO))

    pdf.seccion("Resultado")
    if ultima is None:
        pdf.multi_cell(0, 6, "El talento aún no tiene evaluaciones con IA.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.pares([("Puntuación de IA", f"{ultima['puntuacion_talento_por_ia']} de 100"),
                   ("Nivel de potencial", nivel(ultima["potencial_crecimiento_nivel"])),
                   ("Clasificación 9-box", ultima["clasificacion_9box"]),
                   ("Fecha de evaluación", fecha(ultima["fecha_evaluacion"]))])
        if nota:
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 5, nota, new_x="LMARGIN", new_y="NEXT")
            pdf._texto()
        pdf.seccion("Niveles por criterio")
        criterios = list(analitica.NOMBRES_CRITERIOS.items())
        pdf.tabla(["Criterio", "Nivel"], [[nombre, nivel(ultima[llave])] for llave, nombre in criterios],
                  anchos=(70, 30), colores={(i, 1): COLOR_NIVEL[ultima[llave]] for i, (llave, _) in enumerate(criterios)})
        pdf.seccion("Reporte de IA")
        pdf.multi_cell(0, 6, ultima["reporte_ia"], new_x="LMARGIN", new_y="NEXT")

    pdf.seccion("Línea de tiempo", espacio=80)
    pdf.linea_de_tiempo(talento["fecha_ingreso"], datos["evaluaciones"], datos["eventos"], generado.date())
    pdf.seccion("Eventos")
    if datos["eventos"]:
        pdf.tabla(["Fecha", "Tipo", "Descripción"],
                  [[fecha(e["fecha_evento"]), analitica.TIPOS_EVENTO[e["tipo_evento"]], e["descripcion"]]
                   for e in reversed(datos["eventos"])], anchos=(22, 33, 90))
    else:
        pdf.cell(0, 6, "Sin eventos registrados.")
    return bytes(pdf.output())


def pdf_general(datos, usuario, generado):
    indicadores = datos["indicadores"]
    pdf = _PDF(usuario, generado)
    pdf.titulo("Reporte general de talento")
    pdf.pares([("Fecha de generación", f"{generado:%d/%m/%Y %H:%M}"), *descripcion_filtros(datos["filtros"])])

    pdf.seccion("Indicadores")
    pdf.tabla(["Indicador", "Valor"], _lineas_indicadores(indicadores), anchos=(110, 40),
              alineaciones=("LEFT", "RIGHT"))

    if not datos["distribucion"]:
        pdf.seccion("Resultados")
        pdf.multi_cell(0, 6, "Ningún talento del grupo tiene evaluaciones con IA.", new_x="LMARGIN", new_y="NEXT")
        return bytes(pdf.output())

    pdf.seccion("Distribución por nivel y por área")
    filas = [[d["area"], d["alto"], d["medio"], d["bajo"], d["total"]] for d in datos["distribucion"]]
    filas.append(["Total", *(sum(d[n] for d in datos["distribucion"]) for n in ("alto", "medio", "bajo", "total"))])
    pdf.tabla(["Área", "Alto", "Medio", "Bajo", "Total"], filas, anchos=(70, 20, 20, 20, 20),
              alineaciones=("LEFT", "CENTER", "CENTER", "CENTER", "CENTER"))

    pdf.seccion("Promedio de puntuación por área")
    promedios = [(d["area"], d["promedio"]) for d in datos["distribucion"] if d["promedio"] is not None]
    pdf.barras(sorted(promedios, key=lambda par: par[1], reverse=True), 100)

    pdf.seccion("Matriz 9-box", espacio=85)
    _matriz_9box(pdf, datos["conteo_9box"])

    # La tabla completa cabe en la página o pasa entera a la siguiente
    pdf.seccion("Top 10 de talentos por puntuación", espacio=12 + 8 * (len(datos["top"]) + 1))
    pdf.tabla(["#", "ID", "Nombre", "Área", "Puntos", "Potencial"],
              [[i, t["id_talento"], t["nombre"], t["area"], t["puntuacion"], nivel(t["nivel"])]
               for i, t in enumerate(datos["top"], start=1)],
              anchos=(7, 11, 52, 42, 15, 20), alineaciones=("CENTER", "CENTER", "LEFT", "LEFT", "CENTER", "CENTER"),
              colores={(i, 5): COLOR_NIVEL[t["nivel"]] for i, t in enumerate(datos["top"])})
    return bytes(pdf.output())


def _matriz_9box(pdf, conteo):
    # 3 x 3: potencial en filas (alto arriba) y desempeño en columnas (bajo a la izquierda)
    lado, x0 = 38, pdf.l_margin + 18
    y0 = pdf.get_y() + 2
    maximo = max((conteo[c] for c in evaluaciones.MATRIZ_9BOX.values()), default=0) or 1
    for fila, potencial in enumerate(reversed(analitica.NIVELES)):
        for columna, desempeno in enumerate(analitica.NIVELES):
            nombre = evaluaciones.MATRIZ_9BOX[(potencial, desempeno)]
            x, y = x0 + columna * lado, y0 + fila * lado * 0.55
            intensidad = conteo[nombre] / maximo
            # Del gris claro al azul oscuro según el número de talentos
            color = tuple(round(c1 + (c2 - c1) * intensidad) for c1, c2 in zip(GRIS_CLARO, AZUL))
            pdf.set_fill_color(*color)
            pdf.set_draw_color(*BLANCO)
            pdf.set_line_width(0.8)
            pdf.rect(x, y, lado, lado * 0.55, style="DF")
            pdf.set_text_color(*(BLANCO if intensidad > 0.45 else AZUL))
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_xy(x, y + 3)
            pdf.cell(lado, 8, str(conteo[nombre]), align="C")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_xy(x, y + 12)
            pdf.cell(lado, 5, nombre, align="C")
    pdf.set_text_color(*GRIS_TEXTO)
    pdf.set_font("Helvetica", "", 8)
    for fila, potencial in enumerate(reversed(analitica.NIVELES)):
        pdf.set_xy(pdf.l_margin, y0 + fila * lado * 0.55 + lado * 0.2)
        pdf.cell(17, 5, nivel(potencial), align="R")
    for columna, desempeno in enumerate(analitica.NIVELES):
        pdf.set_xy(x0 + columna * lado, y0 + 3 * lado * 0.55 + 1)
        pdf.cell(lado, 5, nivel(desempeno), align="C")
    pdf.set_xy(x0, y0 + 3 * lado * 0.55 + 6)
    pdf.cell(3 * lado, 5, "Desempeño previo (columnas) · Potencial de crecimiento (filas)", align="C")
    sin_clasificar = conteo.get(evaluaciones.SIN_CLASIFICAR, 0)
    pdf.set_xy(pdf.l_margin, pdf.get_y() + 6)
    if sin_clasificar:
        pdf.cell(0, 5, f"Sin clasificar (sin desempeño previo): {sin_clasificar}")
        pdf.ln(5)
    pdf._texto()


# --- Excel (openpyxl) ---

_ENCABEZADO = PatternFill("solid", fgColor="D9D9D9")


def _hoja(libro, nombre, titulo, generado, encabezados, filas, largas=()):
    # Fila 1: título y fecha; fila 2: encabezados en negritas con fondo gris claro,
    # filtros automáticos e inmovilizados; columnas ajustadas (PRD, 14)
    hoja = libro.create_sheet(nombre)
    hoja.append([f"{titulo} – generado el {generado:%d/%m/%Y %H:%M}"])
    hoja["A1"].font = Font(bold=True, size=13, color="0B1F3A")
    hoja.append(list(encabezados))
    for celda in hoja[2]:
        celda.font = Font(bold=True)
        celda.fill = _ENCABEZADO
    for fila in filas:
        hoja.append([None if valor is not None and not isinstance(valor, str) and pd.isna(valor) else valor
                     for valor in fila])
    for fila in hoja.iter_rows(min_row=3):
        for celda in fila:
            if isinstance(celda.value, (datetime.date, datetime.datetime)):
                celda.number_format = "dd/mm/yyyy"
            if encabezados[celda.column - 1] in largas:
                celda.alignment = Alignment(wrap_text=True, vertical="top")
            else:
                celda.alignment = Alignment(vertical="top")
    hoja.auto_filter.ref = f"A2:{get_column_letter(len(encabezados))}{max(hoja.max_row, 2)}"
    hoja.freeze_panes = "A3"
    for indice, encabezado in enumerate(encabezados, start=1):
        valores = [encabezado] + [fila[indice - 1] for fila in filas]
        ancho = max(10 if isinstance(v, (datetime.date, datetime.datetime)) else len(str(v or "")) for v in valores)
        hoja.column_dimensions[get_column_letter(indice)].width = min(ancho + 2, 80 if encabezado in largas else 45)
    return hoja


def _libro():
    libro = Workbook()
    libro.remove(libro.active)
    return libro


def _guardar(libro):
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def excel_individual(datos, usuario, generado):
    talento = datos["talento"]
    libro = _libro()
    _hoja(libro, "Talento", f"Talento {talento['id_talento']} – {talento['nombre']}", generado, ["Campo", "Valor"],
          [(NOMBRES_CAMPOS[campo], talento[campo]) for campo in _COLUMNAS_TALENTO], largas=("Valor",))
    _hoja(libro, "Evaluaciones", f"Evaluaciones de {talento['nombre']}", generado,
          ["ID evaluación", "Fecha", "Puntuación", "Potencial", "Clasificación 9-box",
           *analitica.NOMBRES_CRITERIOS.values()],
          [(e["id_evaluacion"], e["fecha_evaluacion"], e["puntuacion_talento_por_ia"],
            nivel(e["potencial_crecimiento_nivel"]), e["clasificacion_9box"],
            *(nivel(e[llave]) for llave in analitica.NOMBRES_CRITERIOS)) for e in reversed(datos["evaluaciones"])])
    _hoja(libro, "Reporte IA", f"Reporte de IA de {talento['nombre']}", generado,
          ["Fecha", "Puntuación", "Potencial", "Reporte"],
          [(e["fecha_evaluacion"], e["puntuacion_talento_por_ia"], nivel(e["potencial_crecimiento_nivel"]),
            e["reporte_ia"]) for e in reversed(datos["evaluaciones"])] or [("", "", "", SIN_EVALUACION)],
          largas=("Reporte",))
    return _guardar(libro)


def excel_general(datos, usuario, generado):
    libro = _libro()
    filas = [("Generado por", usuario["nombre"]), *descripcion_filtros(datos["filtros"]),
             *_lineas_indicadores(datos["indicadores"])]
    hoja = _hoja(libro, "Resumen", "Reporte general de talento", generado, ["Concepto", "Valor"], filas)
    # Debajo de los indicadores: distribución por área y matriz 9-box
    hoja.append([])
    hoja.append(["Área", "Alto", "Medio", "Bajo", "Total", "Promedio de puntuación"])
    for celda in hoja[hoja.max_row]:
        celda.font = Font(bold=True)
        celda.fill = _ENCABEZADO
    for d in datos["distribucion"]:
        hoja.append([d["area"], d["alto"], d["medio"], d["bajo"], d["total"], d["promedio"]])
    hoja.append([])
    hoja.append(["Clasificación 9-box", "Talentos"])
    for celda in hoja[hoja.max_row]:
        celda.font = Font(bold=True)
        celda.fill = _ENCABEZADO
    for clasificacion, cantidad in datos["conteo_9box"].items():
        hoja.append([clasificacion, cantidad])
    hoja.column_dimensions["A"].width = max(hoja.column_dimensions["A"].width, 28)
    for columna in "CDEF":
        hoja.column_dimensions[columna].width = 12 if columna != "F" else 24

    encabezados = [*(NOMBRES_CAMPOS[c] for c in _COLUMNAS_TALENTO), "Puntuación", "Nivel de potencial",
                   "Clasificación 9-box", "Fecha de evaluación"]
    _hoja(libro, "Talentos", "Talentos", generado, encabezados,
          [(*(t[c] for c in _COLUMNAS_TALENTO), t["puntuacion_talento_por_ia"], nivel(t["potencial_crecimiento_nivel"]),
            t["clasificacion_9box"] or SIN_EVALUACION, t["fecha_evaluacion"]) for t in datos["talentos"]])
    return _guardar(libro)


# --- Respaldo en texto (E-201 y E-202) ---

def texto_individual(datos, usuario, generado):
    talento = datos["talento"]
    ultima, nota = _evaluacion_detallada(datos)
    lineas = [f"{interfaz.NOMBRE} – Reporte individual de talento", "",
              *(f"{NOMBRES_CAMPOS[c]}: {_valor_texto(talento[c])}" for c in _COLUMNAS_TALENTO), ""]
    if ultima is None:
        lineas += ["Resultado: el talento aún no tiene evaluaciones con IA.", ""]
    else:
        lineas += ["RESULTADO",
                   f"Puntuación de IA: {ultima['puntuacion_talento_por_ia']} de 100",
                   f"Nivel de potencial: {nivel(ultima['potencial_crecimiento_nivel'])}",
                   f"Clasificación 9-box: {ultima['clasificacion_9box']}",
                   f"Fecha de evaluación: {fecha(ultima['fecha_evaluacion'])}", *([nota] if nota else []), "",
                   "NIVELES POR CRITERIO",
                   *(f"- {nombre}: {nivel(ultima[llave])}" for llave, nombre in analitica.NOMBRES_CRITERIOS.items()),
                   "", "REPORTE DE IA", ultima["reporte_ia"], ""]
    lineas += ["EVALUACIONES",
               *(f"- {fecha(e['fecha_evaluacion'])}: {e['puntuacion_talento_por_ia']} puntos, potencial "
                 f"{e['potencial_crecimiento_nivel']}, {e['clasificacion_9box']}" for e in reversed(datos["evaluaciones"])),
               "", "EVENTOS",
               *(f"- {fecha(e['fecha_evento'])} ({analitica.TIPOS_EVENTO[e['tipo_evento']]}): {e['descripcion']}"
                 for e in reversed(datos["eventos"]))]
    return _con_pie(lineas, usuario, generado)


def texto_general(datos, usuario, generado):
    lineas = [f"{interfaz.NOMBRE} – Reporte general de talento", "", "FILTROS",
              *(f"- {filtro}: {valor}" for filtro, valor in descripcion_filtros(datos["filtros"])), "",
              "INDICADORES", *(f"- {dato}: {valor}" for dato, valor in _lineas_indicadores(datos["indicadores"])), "",
              "DISTRIBUCIÓN POR ÁREA (alto / medio / bajo / total / promedio)",
              *(f"- {d['area']}: {d['alto']} / {d['medio']} / {d['bajo']} / {d['total']} / {d['promedio']}"
                for d in datos["distribucion"]), "",
              "MATRIZ 9-BOX", *(f"- {c}: {n}" for c, n in datos["conteo_9box"].items()), "",
              "TOP 10 POR PUNTUACIÓN",
              *(f"{i}. {t['nombre']} (ID {t['id_talento']}, {t['area']}): {t['puntuacion']} puntos, potencial {t['nivel']}"
                for i, t in enumerate(datos["top"], start=1)), "",
              "TALENTOS (ID | nombre | área | correo | teléfono | ingreso | desempeño | puntuación | nivel | 9-box | fecha)",
              *(" | ".join(_valor_texto(v) for v in (
                  t["id_talento"], t["nombre"], t["area"], t["correo"], t["tel_mx"], t["fecha_ingreso"],
                  t["desempeno_previo"], t["puntuacion_talento_por_ia"], t["potencial_crecimiento_nivel"],
                  t["clasificacion_9box"] or SIN_EVALUACION, t["fecha_evaluacion"])) for t in datos["talentos"])]
    return _con_pie(lineas, usuario, generado)


def _valor_texto(valor):
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return ""
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return fecha(valor)
    return str(valor)


def _con_pie(lineas, usuario, generado):
    lineas += ["", f"Generado el {generado:%d/%m/%Y %H:%M} por {usuario['nombre']}", LEYENDA]
    # Con BOM para que el Bloc de notas muestre bien los acentos
    return "\n".join(lineas).encode("utf-8-sig")


# --- Exportación ---

_GENERADORES = {
    ("individual", "pdf"): pdf_individual,
    ("individual", "excel"): excel_individual,
    ("general", "pdf"): pdf_general,
    ("general", "excel"): excel_general,
}
_TEXTO = {"individual": texto_individual, "general": texto_general}


def exportar(usuario, datos, formato, generado=None):
    # Devuelve {"archivo", "contenido", "mime", "codigo"}; codigo es None si el archivo
    # se generó bien, o E-201/E-202 si se entregó el respaldo en texto
    permisos.exigir(usuario, "reportes")
    if datos["tipo"] == "individual":
        permisos.exigir_area(usuario, datos["talento"]["area"])
    generado = generado or datetime.datetime.now()
    configuracion = FORMATOS[formato]
    try:
        contenido = _GENERADORES[(datos["tipo"], formato)](datos, usuario, generado)
        archivo, mime, codigo = nombre_archivo(datos, configuracion["extension"], generado), configuracion["mime"], None
    except Exception as error:
        codigo = configuracion["error"]
        errores.registrar(codigo, error)
        contenido = _TEXTO[datos["tipo"]](datos, usuario, generado)
        archivo, mime = nombre_archivo(datos, ".txt", generado), MIME_TEXTO

    detalle = {"reporte": datos["tipo"], "formato": formato, "archivo": archivo,
               "resultado": codigo or "generado"}
    if datos["tipo"] == "individual":
        id_registro = datos["talento"]["id_talento"]
        if formato == "pdf" and datos.get("evaluacion"):
            detalle["id_evaluacion"] = datos["evaluacion"]["id_evaluacion"]
    else:
        id_registro = None
        detalle["filtros"] = datos["filtros"]
        detalle["talentos"] = datos["indicadores"]["total"]
    with db.transaccion() as cursor:
        bitacora.registrar(cursor, usuario["id_usuario"], "exportacion", "Talentos", id_registro, detalle)
    return {"archivo": archivo, "contenido": contenido, "mime": mime, "codigo": codigo}
