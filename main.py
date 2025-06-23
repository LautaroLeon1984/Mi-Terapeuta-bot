import logging
import os
import re
import time
import datetime
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext
from ejercicio import generar_ejercicio_por_estado

# Configuración básica
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 818432829
openai.api_key = OPENAI_API_KEY

# Base de usuarios
usuarios = {}
respuestas_anteriores = {}
ULTIMO_MENSAJE = {}
MAX_GRATIS = 5
TIEMPO_INACTIVIDAD = 600
base_planes = {}  # user_id: {"inicio": timestamp, "dias": int}

# Configuración de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def notificar_admin(mensaje):
    try:
        if ADMIN_ID:
            await app.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Alerta Admin:\n{mensaje}")
    except Exception as e:
        logger.error(f"Error al notificar al admin: {e}")

# Utilidades

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

def limpiar_formato(texto):
    return re.sub(r'[\*`_]', '', texto)

# Comandos y Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name or "!"
    await update.message.reply_text(
        f"Hola {nombre} 👋 Soy tu terapeuta IA. Podés hablar libremente conmigo las 24hs.\nSi necesitás ayuda, usá /ayuda."
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start – Saludo inicial.\n/ayuda – Mostrar este mensaje.\n/ejercicios – Ejercicio guiado.\n/planes – Ver planes de suscripción."
    )

async def ejercicios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    estado_animo = respuestas_anteriores.get(user_id, {}).get("emocion", "neutral")
    try:
        respuesta = await generar_ejercicio_por_estado(estado_animo)
        for parte in respuesta:
            await update.message.reply_text(parte)
    except Exception as e:
        await notificar_admin(f"Error al generar ejercicio: {str(e)}")
        await update.message.reply_text("Ocurrió un error al generar el ejercicio. Intentalo más tarde.")

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("🗖 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
    ]
    await update.message.reply_text(
        "🚫 Tu acceso gratuito ha finalizado o estás consultando planes. Seleccioná uno para seguir usando el bot:",
        reply_markup=InlineKeyboardMarkup(botones)
    )

# Main Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        mensaje = update.message.text
        ahora = time.time()

        if user_id in ULTIMO_MENSAJE:
            if ahora - ULTIMO_MENSAJE[user_id] > TIEMPO_INACTIVIDAD:
                await update.message.reply_text("⏳ Pasaron más de 10 minutos desde tu último mensaje. ¿Querés continuar o te paso un resumen?")
                return

        ULTIMO_MENSAJE[user_id] = ahora

        if user_id not in usuarios:
            usuarios[user_id] = {"inicio": ahora, "interacciones": 0}

        suscripcion = base_planes.get(user_id)
        if not suscripcion or time.time() > suscripcion["inicio"] + suscripcion["dias"] * 86400:
            if usuarios[user_id]["interacciones"] >= MAX_GRATIS:
                await planes(update, context)
                return

        usuarios[user_id]["interacciones"] += 1

        if user_id not in respuestas_anteriores:
            respuestas_anteriores[user_id] = {"historial": [], "emocion": "neutral"}

        respuestas_anteriores[user_id]["historial"].append({"role": "user", "content": mensaje})

        historial = respuestas_anteriores[user_id]["historial"][-10:]
        respuesta = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "system", "content": "Sos un terapeuta empático que mantiene la coherencia del diálogo."}] + historial
        )

        texto_respuesta = limpiar_formato(respuesta.choices[0].message.content)
        respuestas_anteriores[user_id]["historial"].append({"role": "assistant", "content": texto_respuesta})

        partes = dividir_mensaje_por_puntos(texto_respuesta)
        for parte in partes:
            await update.message.reply_text(parte)

    except Exception as e:
        await notificar_admin(f"Error en handle_message: {str(e)}")
        await update.message.reply_text("Ocurrió un error. Por favor, intentá más tarde.")

# Lanzador del bot
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ejercicios", ejercicios))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
