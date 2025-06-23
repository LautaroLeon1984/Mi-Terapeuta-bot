import logging
import os
import json
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
import openai

# --- Configuración de claves y API ---
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ARCHIVO_USUARIOS = "usuarios.json"

# --- Configuración del log ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Carga de base de datos de usuarios ---
if not os.path.exists(ARCHIVO_USUARIOS):
    with open(ARCHIVO_USUARIOS, "w") as f:
        json.dump({}, f)

with open(ARCHIVO_USUARIOS, "r") as f:
    usuarios = json.load(f)

# --- Servidor Flask para mantener activo Railway ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Función para guardar usuarios ---
def guardar_datos():
    with open(ARCHIVO_USUARIOS, "w") as f:
        json.dump(usuarios, f, indent=2)

# --- Mostrar planes ---
async def mostrar_planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botones = [
        [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
        [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
        [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
        [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
        [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
        [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
    ]
    await update.message.reply_text("🚫 Tu acceso gratuito ha finalizado.\nSeleccioná uno de los planes para seguir usando el bot:", reply_markup=InlineKeyboardMarkup(botones))

# --- Comando /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in usuarios:
        usuarios[user_id] = {
            "interacciones": 0,
            "inicio_plan": None,
            "fin_plan": None,
            "ultimo_mensaje": None
        }
        guardar_datos()
    await update.message.reply_text(
        "Hola 👋 Soy tu terapeuta IA. Estoy disponible 24/7 para escucharte y acompañarte emocionalmente.\n\nTenés 5 mensajes gratuitos. Luego podés elegir un plan para continuar.\n\nEscribí lo que necesites, estoy acá para ayudarte."
    )

# --- Respuesta por IA con control de acceso ---
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    mensaje = update.message.text
    ahora = datetime.now()

    if user_id not in usuarios:
        return await start(update, context)

    usuario = usuarios[user_id]

    # Verificar si tiene plan activo
    if usuario["fin_plan"]:
        fin = datetime.fromisoformat(usuario["fin_plan"])
        if ahora > fin:
            usuario["fin_plan"] = None
            usuario["inicio_plan"] = None

    if not usuario["fin_plan"] and usuario["interacciones"] >= 5:
        return await mostrar_planes(update, context)

    # Procesar respuesta por OpenAI
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sos un terapeuta virtual empático. Brindá respuestas claras, concisas y con sensibilidad emocional."},
                {"role": "user", "content": mensaje}
            ]
        )
        reply = respuesta.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        logging.error(f"Error IA: {e}")
        await update.message.reply_text("⚠️ Ocurrió un error al procesar tu mensaje.")
        return

    # Actualizar datos
    usuario["interacciones"] += 1
    usuario["ultimo_mensaje"] = ahora.isoformat()
    guardar_datos()

    # Verificar inactividad
    if usuario.get("ultimo_mensaje"):
        anterior = datetime.fromisoformat(usuario["ultimo_mensaje"])
        if ahora - anterior > timedelta(minutes=10):
            await update.message.reply_text("¿Querés seguir conversando o preferís un resumen para retomarlo más tarde?")

# --- Inicio del bot ---
if __name__ == "__main__":
    keep_alive()

    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    app_bot.post_init = setup

    print("🤖 Bot terapeuta IA iniciado y esperando mensajes...")
    app_bot.run_polling()
