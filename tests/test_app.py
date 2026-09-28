from streamlit.testing.v1 import AppTest


def test_sin_sesion_muestra_inicio_de_sesion():
    app = AppTest.from_file("../app.py").run()
    assert not app.exception
    assert app.title[0].value == "Sistema de Identificación de Talento de Alto Potencial"
    assert [t.label for t in app.text_input] == ["Usuario", "Contraseña", "Correo registrado"]
