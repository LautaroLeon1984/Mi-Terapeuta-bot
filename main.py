import logging
import os
import re
import time
import datetime
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Configuración
TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = 818432829
openai.api_key = OPENAI_API_KEY

# Estados
usuarios = {}  # {user_id: {"inicio": timestamp, "vencimiento": timestamp, "interacciones": int}}
respuestas_anteriores = {}
ULTIMO_MENSAJE = {}
MAX_GRATIS = 5
TIEMPO_INACTIVIDAD = 600

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Utilidades
async def notificar_admin(mensaje):
    try:
        if ADMIN_ID:
            await app.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Alerta Admin:\n{mensaje}")
    except Exception as e:
        logger.error(f"Error al notificar al admin: {e}")

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

def tiene_acceso(user_id):
    datos = usuarios.get(user_id, {})
    ahora = time.time()
    if "vencimiento" in datos:
        return ahora < datos["vencimiento"]
    return datos.get("interacciones", 0) < MAX_GRATIS

def registrar_usuario(user_id):
    ahora = time.time()
    if user_id not in usuarios:
        usuarios[user_id] = {"inicio": ahora, "interacciones": 0}

# Comandos
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
    try:
        user_id = update.effective_user.id
        estado = "neutro"  # Esto luego será reemplazado con detección real

        mensaje_sistema = "Sos un terapeuta profesional. Generá un ejercicio guiado para una persona que se siente {}. Sé claro, concreto y empático. Evitá títulos innecesarios."
        respuesta = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": mensaje_sistema.format(estado)},
                {"role": "user", "content": "Dame un ejercicio guiado para hoy."}
            ]
        ).choices[0].message.content

        respuesta = limpiar_formato(respuesta)
        partes = dividir_mensaje_por_puntos(respuesta)
        for parte in partes:
            await update.message.reply_text(parte)

    except Exception as e:
        await notificar_admin(f"Error en /ejercicios: {str(e)}")
        await update.message.reply_text("Hubo un error al generar el ejercicio. Intentá más tarde.")

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

# Mensaje libre
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        mensaje = update.message.text
        ahora = time.time()
        registrar_usuario(user_id)
        ULTIMO_MENSAJE[user_id] = ahora

        if not tiene_acceso(user_id):
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

# Lanzador
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("ejercicios", ejercicios))
    app.add_handler(CommandHandler("planes", planes))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
