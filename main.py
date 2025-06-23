import logging
import os
import openai
import asyncio
import json
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# --- Verificación de variables de entorno ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise EnvironmentError("❌ ERROR: OPENAI_API_KEY o TELEGRAM_BOT_TOKEN no están definidas en las variables de entorno")

# --- Configuración inicial ---
openai.api_key = OPENAI_API_KEY
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- Base de datos local ---
DB_PATH = "usuarios.json"
try:
    with open(DB_PATH, "r") as f:
        usuarios = json.load(f)
except FileNotFoundError:
    usuarios = {}

# --- Servidor Flask ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo desde Railway ✅", 200

def keep_alive():
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# --- Planes de suscripción ---
PLANES = [
    [InlineKeyboardButton("🗓️ Plan Semanal – $4.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=21746b5ae9c94be08c0b9abcb9484f0b")],
    [InlineKeyboardButton("📆 Plan Quincenal – $7.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=32e17d17ce334234ac3d5577bfc3fea0")],
    [InlineKeyboardButton("🗓️ Plan Mensual – $12.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=1a92e8b1e31d44b99188505cf835483d")],
    [InlineKeyboardButton("📅 Plan Trimestral – $30.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=9a17a9ac63844309ab87119b56f6f71e")],
    [InlineKeyboardButton("📅 Plan Semestral – $55.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=cff15077ebe84fb88ccd0e20afa29437")],
    [InlineKeyboardButton("📅 Plan Anual – $99.000", url="https://www.mercadopago.com.ar/subscriptions/checkout?preapproval_plan_id=3f7b1e3b69d544f78c7d9862e1391228")],
]

# --- Funciones del bot ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in usuarios:
        usuarios[uid] = {
            "inicio": str(datetime.now()),
            "interacciones": 0,
            "plan_activo": False
        }
        with open(DB_PATH, "w") as f:
            json.dump(usuarios, f)

    bienvenida = (
        "Hola 👋 Soy tu terapeuta IA. Estoy disponible 24/7 para acompañarte con respuestas empáticas, claras y concisas.\n"
        "🧠 Este servicio no reemplaza una terapia profesional.\n"
        "⌛ Tenés 5 consultas gratuitas. Luego podés elegir un plan para continuar.\n"
        "📋 Usá /ayuda si necesitás más información."
    )
    await update.message.reply_text(bienvenida)

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Consultas 24/7 con IA empática. 5 mensajes gratis. Luego, seleccioná un plan. /planes")

async def planes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 Elegí un plan para continuar usando el bot:", reply_markup=InlineKeyboardMarkup(PLANES))

# Detección de inactividad
last_messages = {}

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    now = datetime.now()

    # Inactividad
    if uid in last_messages:
        if now - last_messages[uid] > timedelta(minutes=10):
            await update.message.reply_text("⏳ ¿Querés seguir conversando o preferís un resumen?")
    last_messages[uid] = now

    # Registro de usuario y conteo
    if uid not in usuarios:
        usuarios[uid] = {"inicio": str(now), "interacciones": 0, "plan_activo": False}

    if not usuarios[uid]["plan_activo"] and usuarios[uid]["interacciones"] >= 5:
        await update.message.reply_text(
            "🚫 Tu acceso gratuito ha finalizado.",
            reply_markup=InlineKeyboardMarkup(PLANES)
        )
        return

    # Consulta a ChatGPT
    try:
        prompt = update.message.text
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sos un terapeuta empático, claro y conciso."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
        usuarios[uid]["interacciones"] += 1
        with open(DB_PATH, "w") as f:
            json.dump(usuarios, f)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Hubo un error al procesar tu mensaje.")

# --- Inicialización ---
if __name__ == "__main__":
    keep_alive()
    app_bot = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    async def setup():
        await app_bot.bot.delete_webhook(drop_pending_updates=True)

    app_bot.post_init = setup

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("ayuda", ayuda))
    app_bot.add_handler(CommandHandler("planes", planes))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    print("🤖 Bot iniciado y esperando mensajes...")
    app_bot.run_polling()
