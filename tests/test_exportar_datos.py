import datetime
import decimal

import exportar_datos


def test_literales():
    assert exportar_datos.literal(None) == "NULL"
    assert exportar_datos.literal(42) == "42"
    assert exportar_datos.literal(decimal.Decimal("3.5")) == "3.5"
    assert exportar_datos.literal(datetime.date(2026, 10, 14)) == "'2026-10-14'"
    assert exportar_datos.literal(datetime.datetime(2026, 10, 14, 9, 5)) == "'2026-10-14 09:05:00'"
    assert exportar_datos.literal(b"\x89PNG") == "0x89504e47"
    assert exportar_datos.literal(b"") == "''"
    assert exportar_datos.literal('Dijo "sí" y l\'otro\\\n') == "'Dijo \"sí\" y l''otro\\\\\\n'"


def test_inserts_por_grupos():
    registros = [{"id": i, "nombre": f"T{i}"} for i in range(1, 121)]
    sentencias = list(exportar_datos.inserts("Talentos_x", ["id", "nombre"], registros))
    assert len(sentencias) == 3
    assert sentencias[0].startswith("INSERT INTO Talentos_x (id, nombre) VALUES\n    (1, 'T1'),")
    # Las tablas con imágenes van de una fila por sentencia
    assert len(list(exportar_datos.inserts("Manual_imagenes", ["id", "nombre"], registros[:3]))) == 3
