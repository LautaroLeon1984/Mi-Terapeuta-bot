import logging
import os
import re
import time
import datetime
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext

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
    texto = (
        "🧘‍♀️ Ejercicio sugerido:\n"
        "Claro, aquí tienes un ejercicio breve y relajante que puede ayudar a alguien que se siente neutral a reconectar con sus emociones y sensaciones físicas:\n\n"
        "Ejercicio de Escaneo Corporal y Respiración Consciente\n\n"
        "1. Encuentra un Lugar Tranquilo: Siéntate o acuéstate en un lugar cómodo donde no te molesten durante unos minutos.\n"
        "2. Cierra los Ojos: Cierra los ojos suavemente para centrarte en tu interior y desconectarte del entorno.\n"
        "3. Respira Profundamente: Inhala profundamente por la nariz, contando hasta cuatro. Sostén la respiración por un momento y luego exhala lentamente por la boca, contando hasta seis. Repite este ciclo de respiración tres veces.\n"
        "4. Escaneo Corporal: Comienza a prestar atención a tu cuerpo, empezando por los dedos de los pies. Con cada respiración, lleva tu atención lentamente hacia arriba, pasando por cada parte del cuerpo.\n"
        "5. Cierre: Una vez que llegues a la cabeza, toma una respiración profunda final y abre los ojos lentamente. Observa cómo te sentís."
    )
    texto = limpiar_formato(texto)
    partes = dividir_mensaje_por_puntos(texto)
    for parte in partes:
        await update.message.reply_text(parte)

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
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
        ULTIMO_MENSAJE[user_id] = ahora

        if user_id not in usuarios:
            usuarios[user_id] = {"inicio": ahora, "interacciones": 0}

        if usuarios[user_id]["interacciones"] >= MAX_GRATIS:
            await planes(update, context)
            return

        usuarios[user_id]["interacciones"] += 1

        respuesta = await consulta_a_openai(mensaje)
        respuesta = limpiar_formato(respuesta)

        partes = dividir_mensaje_por_puntos(respuesta)
        for parte in partes:
            await update.message.reply_text(parte)

    except Exception as e:
        await notificar_admin(f"Error en handle_message: {str(e)}")
        await update.message.reply_text("Ocurrió un error. Por favor, intentá más tarde.")

async def consulta_a_openai(texto):
    respuesta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Sos un terapeuta que responde con empatía, claridad y concisión."},
            {"role": "user", "content": texto},
        ]
    )
    return respuesta.choices[0].message.content

# Lanzador del bot
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ejercicios", ejercicios))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
