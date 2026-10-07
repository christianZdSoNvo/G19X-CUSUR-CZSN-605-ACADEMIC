from streamlit.testing.v1 import AppTest


def test_sin_sesion_muestra_inicio_de_sesion():
    app = AppTest.from_file("../app.py").run()
    assert not app.exception
    # El nombre del sistema va en el logo
    assert app.get("image") and "Talent Overview System" in app.caption[0].value
    assert [t.label for t in app.text_input] == ["Usuario", "Contraseña", "Correo registrado"]
