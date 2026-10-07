import io

from PIL import Image, ImageOps

from backend import errores, manuales

# Fotos de perfil de talentos y usuarios. Se aceptan PNG o JPG de hasta 5 MB (E-402,
# igual que los manuales) y se guardan recortadas en cuadro de 400 x 400 en JPG, para
# que la BD y las pantallas no carguen imágenes pesadas.

LADO = 400


def preparar(contenido):
    # Devuelve la foto lista para guardar o lanza E-402
    manuales.validar_imagen(contenido)
    try:
        imagen = ImageOps.exif_transpose(Image.open(io.BytesIO(contenido)))
        imagen = ImageOps.fit(imagen.convert("RGB"), (LADO, LADO))
    except (OSError, ValueError) as error:
        raise errores.ErrorSistema("E-402") from error
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", quality=85)
    return salida.getvalue()
