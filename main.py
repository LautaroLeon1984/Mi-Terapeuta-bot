import logging
import os
import re
import time
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Configuración y claves
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 818432829
openai.api_key = OPENAI_API_KEY

# Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Estados globales
usuarios = {}
historial = {}
ULTIMO_MENSAJE = {}
MAX_GRATIS = 5
TIEMPO_INACTIVIDAD = 600

# Utilidades

def limpiar_formato(texto):
    return re.sub(r'[\*`_]', '', texto)

def dividir_mensaje_por_puntos(texto, limite=4095):
    partes = []
    secciones = re.split(r'(?<=\n)(?=\d+\.\s)', texto)
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

async def notificar_admin(mensaje):
    try:
        if ADMIN_ID:
            await app.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Alerta Admin:\n{mensaje}")
    except Exception as e:
        logger.error(f"Error al notificar al admin: {e}")

# GPT
async def consulta_a_openai(user_id, mensaje):
    historial.setdefault(user_id, [])
    historial[user_id].append({"role": "user", "content": mensaje})

    prompt = [{"role": "system", "content": "Sos un terapeuta empático que acompaña emocionalmente con claridad."}]
    prompt.extend(historial[user_id][-10:])

    respuesta = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=prompt
    )

    texto = respuesta.choices[0].message.content
    historial[user_id].append({"role": "assistant", "content": texto})
    return texto

async def generar_ejercicio_por_estado(estado):
    prompt = (
        f"Actuás como terapeuta. Sugiere un ejercicio guiado breve (respiración, relajación, meditación o atención plena) "
        f"para una persona que se siente '{estado}'. Debe ser claro, empático, realizable en casa, no invasivo, en español. "
        f"Redactalo en 4 a 6 pasos simples con encabezado."
    )

    respuesta = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Sos un terapeuta empático que sugiere ejercicios guiados."},
            {"role": "user", "content": prompt},
        ]
    )
    contenido = respuesta.choices[0].message.content
    limpio = limpiar_formato(contenido)
    return dividir_mensaje_por_puntos(limpio)

# Comandos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nombre = update.effective_user.first_name or "👤"
    usuarios[user_id] = {"inicio": time.time(), "interacciones": 0, "ultima_emocion": "neutral"}
    historial[user_id] = []
    await update.message.reply_text(
        f"Hola {nombre} 👋 Soy tu terapeuta IA. Podés hablar libremente conmigo las 24hs.\nUsá /ayuda para ver opciones."
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start – Iniciar conversación\n"
        "/ayuda – Mostrar este menú\n"
        "/ejercicio – Recibir un ejercicio guiado\n"
        "/planes – Ver planes de suscripción"
    )

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [[InlineKeyboardButton("Plan Mensual", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")]]
    await update.message.reply_text(
        "Tu acceso gratuito ha finalizado o estás consultando planes. Seleccioná uno para continuar:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    emocion = usuarios.get(user_id, {}).get("ultima_emocion", "neutral")
    try:
        partes = await generar_ejercicio_por_estado(emocion)
        for parte in partes:
            await update.message.reply_text(parte)
    except Exception as e:
        await notificar_admin(f"Error al generar ejercicio: {str(e)}")
        await update.message.reply_text("Ocurrió un error al generar el ejercicio. Intentalo más tarde.")

# Handler general
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        mensaje = update.message.text
        ahora = time.time()

        if user_id not in usuarios:
            usuarios[user_id] = {"inicio": ahora, "interacciones": 0, "ultima_emocion": "neutral"}
            historial[user_id] = []

        if usuarios[user_id]["interacciones"] >= MAX_GRATIS:
            await planes(update, context)
            return

        usuarios[user_id]["interacciones"] += 1
        ULTIMO_MENSAJE[user_id] = ahora

        respuesta = await consulta_a_openai(user_id, mensaje)
        if "emocion" in mensaje.lower():
            usuarios[user_id]["ultima_emocion"] = mensaje.lower()

        respuesta = limpiar_formato(respuesta)
        partes = dividir_mensaje_por_puntos(respuesta)
        for parte in partes:
            await update.message.reply_text(parte)

    except Exception as e:
        await notificar_admin(f"Error en mensaje: {str(e)}")
        await update.message.reply_text("Ocurrió un error. Intentalo nuevamente en unos minutos.")

# Lanzador
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ejercicio", ejercicios))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
