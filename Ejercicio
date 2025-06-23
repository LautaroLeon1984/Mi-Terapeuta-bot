import re
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

# Utilidad para limpiar texto de formato innecesario (negritas, etc.)
def limpiar_formato(texto):
    return re.sub(r'[\*`_]', '', texto)

# Dividir el mensaje para no cortar frases en Telegram (máximo 4095 caracteres)
def dividir_mensaje_por_puntos(texto, limite=4095):
    partes = []
    secciones = re.split(r'(?<=\n)(?=\d+\.\s)', texto)  # separa por puntos enumerados
    mensaje_actual = ""
    for seccion in secciones:
        if len(mensaje_actual + seccion) <= limite:
            mensaje_actual += seccion
        else:
            partes.append(mensaje_actual.strip())
            mensaje_actual = seccion
    if mensaje_actual:
        partes.append(mensaje_actual.strip())
    return partes

# Función principal: generar un ejercicio guiado personalizado
def generar_ejercicio_por_estado(estado):
    prompt = (
        f"Actuás como terapeuta. Sugiere un ejercicio guiado breve (respiración, relajación, atención plena, movimiento físico u otra técnica emocional) "
        f"para una persona que se siente '{estado}'. Debe ser claro, empático, fácil de hacer en casa, no invasivo. "
        f"Usa tono cálido y accesible, en español. Redactalo en 4 a 6 pasos simples con encabezado."
    )

    respuesta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Sos un terapeuta empático que sugiere ejercicios guiados con claridad y contención emocional."},
            {"role": "user", "content": prompt},
        ]
    )
    contenido = respuesta.choices[0].message.content
    limpio = limpiar_formato(contenido)
    return dividir_mensaje_por_puntos(limpio)
