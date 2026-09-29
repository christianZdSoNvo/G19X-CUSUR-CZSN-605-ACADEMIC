import reset_admin

ANA = {"id_usuario": 1, "nombre": "Ana", "usuario": "ana"}
LUIS = {"id_usuario": 5, "nombre": "Luis", "usuario": "luis"}


def test_un_solo_administrador_se_elige_solo():
    assert reset_admin.elegir([ANA]) == (ANA, None)


def test_varios_administradores_piden_usuario():
    administrador, problema = reset_admin.elegir([ANA, LUIS])
    assert administrador is None and "--usuario" in problema
    assert reset_admin.elegir([ANA, LUIS], "luis") == (LUIS, None)


def test_usuario_que_no_es_administrador():
    administrador, problema = reset_admin.elegir([ANA], "pedro")
    assert administrador is None and "pedro" in problema


def test_sin_administradores():
    assert reset_admin.elegir([])[0] is None
